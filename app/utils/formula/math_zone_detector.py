"""
Módulo de detecção de zonas matemáticas em páginas de PDF.

Este módulo identifica áreas (bounding boxes) onde provavelmente existem
fórmulas matemáticas, usando heurísticas baseadas em:
1. Densidade de caracteres matemáticos
2. Padrões de fonte (Symbol, Cambria Math, etc.)
3. Posição na página (fórmulas em bloco geralmente são centralizadas)
4. Características visuais do texto

A detecção é feita SEM uso de ML/IA, apenas com heurísticas rápidas e leves.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Set, Optional, Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ZoneType(Enum):
    """Tipo de zona matemática detectada."""
    INLINE = "inline"           # Fórmula inline (no meio do texto)
    DISPLAY = "display"         # Fórmula em bloco (centralizada/separada)
    EQUATION = "equation"       # Equação completa (com =)
    FRACTION = "fraction"       # Fração detectada
    MATRIX = "matrix"           # Matriz ou tabela matemática


@dataclass
class MathZone:
    """Representa uma zona matemática detectada."""
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    zone_type: ZoneType
    confidence: float  # 0.0 a 1.0
    page_num: int
    hints: List[str] = field(default_factory=list)  # Razões da detecção


@dataclass
class MathZoneConfig:
    """Configuração do detector de zonas matemáticas."""
    # Thresholds de detecção
    min_math_density: float = 0.15       # Mínimo de chars matemáticos/total
    min_confidence: float = 0.4          # Confiança mínima para reportar

    # Fontes matemáticas conhecidas
    math_fonts: Set[str] = field(default_factory=lambda: {
        'symbol', 'cambria math', 'math', 'cmmi', 'cmsy', 'cmex',
        'stix', 'asana', 'xits', 'latin modern math', 'dejavu math',
        'libertinus math', 'fira math', 'garamond math'
    })

    # Comportamento
    merge_adjacent: bool = True          # Fundir zonas adjacentes
    merge_threshold: float = 20.0        # Distância máxima para fusão (pixels)

    # Limites
    min_zone_width: float = 10.0         # Largura mínima de zona
    min_zone_height: float = 8.0         # Altura mínima de zona


# Caracteres matemáticos para detecção
MATH_CHARS = set(
    # Operadores básicos
    '+-×÷·±∓=≠≈≡≤≥<>∞'
    # Somatórios, produtos, integrais
    '∑∏∫∬∭∮∂∇'
    # Raízes e potências
    '√∛∜'
    # Conjuntos
    '∈∉⊂⊃⊆⊇∩∪∅'
    # Lógica
    '∀∃∄¬∧∨→←↔⇒⇐⇔'
    # Setas
    '→←↑↓↔↕⇒⇐⇑⇓⇔'
    # Letras gregas (minúsculas)
    'αβγδεζηθικλμνξοπρστυφχψω'
    # Letras gregas (maiúsculas)
    'ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ'
    # Símbolos especiais
    '°′″‰∝∠∥⊥'
    # Subscritos/superscritos Unicode
    '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ'
    '₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓ'
)

# Caracteres que indicam contexto matemático
MATH_CONTEXT_CHARS = set('^_{}[]()/')

# Padrões regex para detecção
MATH_PATTERNS = {
    'fraction': re.compile(r'[a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω]+\s*/\s*[a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω]+'),
    'equation': re.compile(r'[a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω\(\)]+\s*[=<>≤≥≠]\s*[a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω\(\)]+'),
    'function': re.compile(r'\b(f|g|h|y)\s*\(\s*[a-zA-Z]\s*\)\s*='),
    'sqrt': re.compile(r'√|\\sqrt'),
    'power': re.compile(r'[a-zA-Z0-9]\s*[\^²³⁴⁵⁶⁷⁸⁹]'),
    'subscript': re.compile(r'[a-zA-Z]\s*[₀₁₂₃₄₅₆₇₈₉ₐₑₒₓₙ]'),
    'sum_prod': re.compile(r'[∑∏∫]'),
    'limit': re.compile(r'\blim\b|\blim_'),
    'trig': re.compile(r'\b(sen|cos|tan|cot|sec|csc|sin|arcsen|arccos|arctan)\b', re.IGNORECASE),
    'log': re.compile(r'\b(log|ln|lg|exp)\b', re.IGNORECASE),
    'set_notation': re.compile(r'[∈∉⊂⊃∩∪]|\\in|\\subset'),
    'derivative': re.compile(r"[a-zA-Z]'\s*\(|d[a-zA-Z]/d[a-zA-Z]|∂"),
    # Caracteres matemáticos Unicode (fontes especiais)
    'unicode_math': re.compile(r'[𝑎-𝑧𝐴-𝑍𝟎-𝟗𝛼-𝜔]'),
}

# Caracteres Unicode matemáticos itálicos (U+1D400 range)
MATH_ITALIC_RANGE = set(chr(c) for c in range(0x1D400, 0x1D7FF + 1))


class MathZoneDetector:
    """
    Detecta zonas matemáticas em páginas de PDF.

    Usa heurísticas baseadas em:
    - Densidade de caracteres matemáticos
    - Fontes matemáticas
    - Padrões de texto (equações, frações, funções)
    - Posição na página
    """

    def __init__(self, config: Optional[MathZoneConfig] = None):
        """
        Inicializa o detector.

        Args:
            config: Configuração opcional. Usa padrão se não fornecida.
        """
        self.config = config or MathZoneConfig()
        self._stats = {
            'zones_detected': 0,
            'pages_processed': 0,
        }

    def detect_zones_in_blocks(
        self,
        blocks: List[Dict],
        page_num: int,
        page_width: float = 612.0,
        page_height: float = 792.0
    ) -> List[MathZone]:
        """
        Detecta zonas matemáticas em blocos de texto extraídos.

        Args:
            blocks: Lista de blocos com 'text', 'bbox', 'font_name', etc.
            page_num: Número da página
            page_width: Largura da página em pontos
            page_height: Altura da página em pontos

        Returns:
            Lista de MathZone detectadas
        """
        zones = []

        for block in blocks:
            text = block.get('text', '')
            bbox = block.get('bbox', (0, 0, 0, 0))
            font_name = block.get('font_name', '').lower()

            # Calcular score de cada bloco
            score, hints, zone_type = self._analyze_block(
                text, bbox, font_name, page_width, page_height
            )

            if score >= self.config.min_confidence:
                zone = MathZone(
                    bbox=tuple(bbox),
                    zone_type=zone_type,
                    confidence=min(score, 1.0),
                    page_num=page_num,
                    hints=hints
                )
                zones.append(zone)

        # Fundir zonas adjacentes se configurado
        if self.config.merge_adjacent and len(zones) > 1:
            zones = self._merge_adjacent_zones(zones)

        self._stats['zones_detected'] += len(zones)
        self._stats['pages_processed'] += 1

        return zones

    def _analyze_block(
        self,
        text: str,
        bbox: Tuple[float, float, float, float],
        font_name: str,
        page_width: float,
        page_height: float
    ) -> Tuple[float, List[str], ZoneType]:
        """
        Analisa um bloco de texto para determinar se é matemático.

        Returns:
            Tupla (score, hints, zone_type)
        """
        if not text or len(text.strip()) < 2:
            return 0.0, [], ZoneType.INLINE

        score = 0.0
        hints = []
        zone_type = ZoneType.INLINE

        # 1. Densidade de caracteres matemáticos
        math_count = sum(1 for c in text if c in MATH_CHARS or c in MATH_ITALIC_RANGE)
        context_count = sum(1 for c in text if c in MATH_CONTEXT_CHARS)
        total_chars = len(text.replace(' ', ''))

        if total_chars > 0:
            density = (math_count + context_count * 0.5) / total_chars
            if density >= self.config.min_math_density:
                score += density * 0.4
                hints.append(f"math_density={density:.2f}")

        # 2. Fonte matemática
        if any(mf in font_name for mf in self.config.math_fonts):
            score += 0.3
            hints.append(f"math_font={font_name}")

        # 3. Padrões específicos
        for pattern_name, pattern in MATH_PATTERNS.items():
            if pattern.search(text):
                pattern_score = self._get_pattern_score(pattern_name)
                score += pattern_score
                hints.append(f"pattern:{pattern_name}")

                # Determinar tipo de zona
                if pattern_name == 'equation':
                    zone_type = ZoneType.EQUATION
                elif pattern_name == 'fraction':
                    zone_type = ZoneType.FRACTION

        # 4. Posição na página (fórmulas display são centralizadas)
        x0, y0, x1, y1 = bbox
        block_center_x = (x0 + x1) / 2
        page_center_x = page_width / 2

        # Se está próximo do centro horizontal
        if abs(block_center_x - page_center_x) < page_width * 0.15:
            # E não ocupa toda a largura (não é parágrafo)
            block_width = x1 - x0
            if block_width < page_width * 0.6:
                score += 0.1
                hints.append("centered")
                zone_type = ZoneType.DISPLAY

        # 5. Verificar caracteres Unicode matemáticos itálicos
        unicode_math_count = sum(1 for c in text if c in MATH_ITALIC_RANGE)
        if unicode_math_count > 0:
            score += 0.2
            hints.append("unicode_math_chars")

        # 6. Verificar se contém apenas números e operadores (expressão isolada)
        stripped = text.strip()
        if self._is_isolated_expression(stripped):
            score += 0.15
            hints.append("isolated_expression")

        return score, hints, zone_type

    def _get_pattern_score(self, pattern_name: str) -> float:
        """Retorna o score para cada tipo de padrão."""
        scores = {
            'fraction': 0.25,
            'equation': 0.3,
            'function': 0.35,
            'sqrt': 0.3,
            'power': 0.2,
            'subscript': 0.2,
            'sum_prod': 0.35,
            'limit': 0.3,
            'trig': 0.25,
            'log': 0.2,
            'set_notation': 0.25,
            'derivative': 0.3,
            'unicode_math': 0.2,
        }
        return scores.get(pattern_name, 0.1)

    def _is_isolated_expression(self, text: str) -> bool:
        """Verifica se o texto é uma expressão matemática isolada."""
        # Remover espaços
        text = text.replace(' ', '')

        if len(text) < 3:
            return False

        # Contar tipos de caracteres
        letters = sum(1 for c in text if c.isalpha() or c in MATH_ITALIC_RANGE)
        digits = sum(1 for c in text if c.isdigit())
        operators = sum(1 for c in text if c in MATH_CHARS or c in '+-*/=^_()[]{}')

        total = letters + digits + operators
        if total == 0:
            return False

        # É expressão se tem operadores e proporção adequada
        if operators > 0:
            operator_ratio = operators / total
            if 0.1 <= operator_ratio <= 0.6:
                return True

        return False

    def _merge_adjacent_zones(self, zones: List[MathZone]) -> List[MathZone]:
        """
        Funde zonas adjacentes que provavelmente são parte da mesma fórmula.
        """
        if not zones:
            return zones

        # Ordenar por posição Y, depois X
        sorted_zones = sorted(zones, key=lambda z: (z.bbox[1], z.bbox[0]))

        merged = []
        current = sorted_zones[0]

        for next_zone in sorted_zones[1:]:
            if self._should_merge(current, next_zone):
                current = self._merge_two_zones(current, next_zone)
            else:
                merged.append(current)
                current = next_zone

        merged.append(current)
        return merged

    def _should_merge(self, zone1: MathZone, zone2: MathZone) -> bool:
        """Verifica se duas zonas devem ser fundidas."""
        # Mesma página
        if zone1.page_num != zone2.page_num:
            return False

        x0_1, y0_1, x1_1, y1_1 = zone1.bbox
        x0_2, y0_2, x1_2, y1_2 = zone2.bbox

        # Distância vertical
        vertical_gap = y0_2 - y1_1
        if vertical_gap > self.config.merge_threshold:
            return False

        # Verificar sobreposição horizontal
        horizontal_overlap = min(x1_1, x1_2) - max(x0_1, x0_2)
        if horizontal_overlap < -self.config.merge_threshold:
            return False

        return True

    def _merge_two_zones(self, zone1: MathZone, zone2: MathZone) -> MathZone:
        """Funde duas zonas em uma."""
        x0 = min(zone1.bbox[0], zone2.bbox[0])
        y0 = min(zone1.bbox[1], zone2.bbox[1])
        x1 = max(zone1.bbox[2], zone2.bbox[2])
        y1 = max(zone1.bbox[3], zone2.bbox[3])

        # Usar maior confiança
        confidence = max(zone1.confidence, zone2.confidence)

        # Combinar hints
        hints = list(set(zone1.hints + zone2.hints))

        # Usar tipo mais específico
        zone_type = zone1.zone_type
        if zone2.zone_type in (ZoneType.EQUATION, ZoneType.DISPLAY):
            zone_type = zone2.zone_type

        return MathZone(
            bbox=(x0, y0, x1, y1),
            zone_type=zone_type,
            confidence=confidence,
            page_num=zone1.page_num,
            hints=hints
        )

    def is_math_text(self, text: str) -> Tuple[bool, float]:
        """
        Verifica rapidamente se um texto contém matemática.

        Args:
            text: Texto a verificar

        Returns:
            Tupla (is_math, confidence)
        """
        if not text or len(text.strip()) < 2:
            return False, 0.0

        score, hints, _ = self._analyze_block(
            text, (0, 0, 100, 20), '', 612, 792
        )

        return score >= self.config.min_confidence, score

    def get_stats(self) -> Dict:
        """Retorna estatísticas de processamento."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'zones_detected': 0,
            'pages_processed': 0,
        }


def get_math_zone_detector(config: Optional[MathZoneConfig] = None) -> MathZoneDetector:
    """Factory function para obter instância do detector."""
    return MathZoneDetector(config)


def detect_math_zones_in_text(text: str) -> List[Tuple[int, int, float]]:
    """
    Detecta spans de texto matemático dentro de uma string.

    Args:
        text: Texto a analisar

    Returns:
        Lista de tuplas (start, end, confidence) para cada zona detectada
    """
    detector = MathZoneDetector()
    zones = []

    # Usar padrões para encontrar spans
    for pattern_name, pattern in MATH_PATTERNS.items():
        for match in pattern.finditer(text):
            start, end = match.span()
            score = detector._get_pattern_score(pattern_name)
            zones.append((start, end, score))

    # Remover sobreposições, mantendo maior score
    if not zones:
        return []

    zones.sort(key=lambda x: x[0])
    merged = [zones[0]]

    for start, end, score in zones[1:]:
        last_start, last_end, last_score = merged[-1]

        # Verifica sobreposição
        if start < last_end:
            # Mantém o de maior score ou expande
            if score > last_score:
                merged[-1] = (last_start, max(last_end, end), score)
            else:
                merged[-1] = (last_start, max(last_end, end), last_score)
        else:
            merged.append((start, end, score))

    return merged
