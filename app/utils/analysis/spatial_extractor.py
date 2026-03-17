"""
Módulo de extração espacial de texto de PDFs.

Este módulo implementa a estratégia de "Reordenação Espacial" (Spatial Sorting)
para resolver o problema de "PDF Spaghetti" onde caracteres são escritos fora
de ordem no arquivo PDF, mas aparecem corretos visualmente.

A solução ignora o fluxo de texto do PDF e força uma reordenação baseada em
coordenadas (X, Y), lendo da esquerda para direita, de cima para baixo.

Características:
- Extração granular de palavras/caracteres com coordenadas
- Reordenação espacial com tolerância vertical (Fuzzy Y)
- Agrupamento em linhas virtuais para lidar com sub/superscritos
- Baixo consumo de memória (processa página por página)
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set
from enum import Enum
import logging

try:
    import fitz
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)


class TextElement(Enum):
    """Tipo de elemento de texto."""
    WORD = "word"
    CHAR = "char"
    SPAN = "span"


@dataclass
class SpatialWord:
    """Representa uma palavra/fragmento com suas coordenadas espaciais."""
    text: str
    x0: float  # Posição esquerda
    y0: float  # Posição superior (top)
    x1: float  # Posição direita
    y1: float  # Posição inferior (bottom)
    font_size: float = 12.0
    font_name: str = ""
    flags: int = 0  # Flags de fonte (bold, italic, etc.)

    @property
    def width(self) -> float:
        """Largura do elemento."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Altura do elemento."""
        return self.y1 - self.y0

    @property
    def center_x(self) -> float:
        """Centro horizontal."""
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        """Centro vertical."""
        return (self.y0 + self.y1) / 2

    @property
    def baseline(self) -> float:
        """Estimativa da linha base (80% da altura a partir do topo)."""
        return self.y0 + self.height * 0.8


@dataclass
class SpatialLine:
    """Representa uma linha reconstruída espacialmente."""
    words: List[SpatialWord] = field(default_factory=list)
    y_group: int = 0  # Grupo vertical (linha virtual)

    @property
    def text(self) -> str:
        """Texto da linha reconstruído."""
        if not self.words:
            return ""
        return " ".join(w.text for w in self.words)

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Bounding box da linha."""
        if not self.words:
            return (0, 0, 0, 0)
        x0 = min(w.x0 for w in self.words)
        y0 = min(w.y0 for w in self.words)
        x1 = max(w.x1 for w in self.words)
        y1 = max(w.y1 for w in self.words)
        return (x0, y0, x1, y1)


@dataclass
class SpatialExtractorConfig:
    """Configuração do extrator espacial."""
    # Tolerância vertical para agrupar em linhas (pixels)
    # Se muito alto: confunde numerador com denominador
    # Se muito baixo: separa expoentes da base
    vertical_tolerance: float = 3.0

    # Tolerância horizontal para juntar palavras (pixels)
    horizontal_gap_threshold: float = 10.0

    # Modo de extração
    extract_mode: TextElement = TextElement.WORD

    # Normalizar espaços
    normalize_spaces: bool = True

    # Remover hifens de quebra de linha
    remove_line_hyphens: bool = True

    # Mínimo de caracteres para considerar
    min_text_length: int = 1


class SpatialExtractor:
    """
    Extrai texto de PDFs com reordenação espacial.

    Resolve o problema de "PDF Spaghetti" onde o texto interno está
    desordenado mas visualmente correto.
    """

    def __init__(self, config: Optional[SpatialExtractorConfig] = None):
        """
        Inicializa o extrator.

        Args:
            config: Configuração opcional
        """
        self.config = config or SpatialExtractorConfig()
        self._stats = {
            'words_extracted': 0,
            'lines_reconstructed': 0,
            'pages_processed': 0,
        }

    def extract_words_from_page(self, page) -> List[SpatialWord]:
        """
        Extrai todas as palavras de uma página com suas coordenadas.

        Args:
            page: Objeto fitz.Page

        Returns:
            Lista de SpatialWord
        """
        if fitz is None:
            logger.error("PyMuPDF (fitz) não está instalado")
            return []

        words = []

        try:
            # Extrair dicionário detalhado
            text_dict = page.get_text("dict")

            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # Apenas blocos de texto
                    continue

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_text = span.get("text", "").strip()
                        if not span_text:
                            continue

                        bbox = span.get("bbox", [0, 0, 0, 0])

                        # Criar SpatialWord para cada span
                        word = SpatialWord(
                            text=span_text,
                            x0=bbox[0],
                            y0=bbox[1],
                            x1=bbox[2],
                            y1=bbox[3],
                            font_size=span.get("size", 12.0),
                            font_name=span.get("font", ""),
                            flags=span.get("flags", 0),
                        )
                        words.append(word)

            self._stats['words_extracted'] += len(words)

        except Exception as e:
            logger.error(f"Erro ao extrair palavras: {e}")

        return words

    def extract_words_from_bbox(
        self,
        page,
        bbox: Tuple[float, float, float, float]
    ) -> List[SpatialWord]:
        """
        Extrai palavras apenas de uma área específica da página.

        Args:
            page: Objeto fitz.Page
            bbox: Área a extrair (x0, y0, x1, y1)

        Returns:
            Lista de SpatialWord dentro da área
        """
        all_words = self.extract_words_from_page(page)

        x0, y0, x1, y1 = bbox

        # Filtrar palavras dentro da bbox
        filtered = []
        for word in all_words:
            # Verificar se o centro da palavra está dentro da bbox
            if (x0 <= word.center_x <= x1 and
                y0 <= word.center_y <= y1):
                filtered.append(word)

        return filtered

    def reorder_spatially(
        self,
        words: List[SpatialWord],
        tolerance_y: Optional[float] = None
    ) -> List[SpatialWord]:
        """
        Reordena palavras espacialmente (esquerda→direita, cima→baixo).

        Usa "linhas virtuais" com tolerância vertical para agrupar
        elementos que estão aproximadamente na mesma altura.

        Args:
            words: Lista de palavras a reordenar
            tolerance_y: Tolerância vertical (pixels). Se None, usa config.

        Returns:
            Lista de palavras reordenadas
        """
        if not words:
            return []

        tolerance = tolerance_y or self.config.vertical_tolerance

        # Função de chave para ordenação
        def sort_key(word: SpatialWord) -> Tuple[int, float]:
            # Agrupa verticalmente em "baldes" baseado na tolerância
            y_group = round(word.y0 / tolerance)
            return (y_group, word.x0)

        return sorted(words, key=sort_key)

    def reconstruct_text(
        self,
        words: List[SpatialWord],
        tolerance_y: Optional[float] = None
    ) -> str:
        """
        Reconstrói texto a partir de palavras reordenadas espacialmente.

        Args:
            words: Lista de palavras
            tolerance_y: Tolerância vertical

        Returns:
            Texto reconstruído
        """
        if not words:
            return ""

        sorted_words = self.reorder_spatially(words, tolerance_y)

        # Juntar com espaços
        result = " ".join(w.text for w in sorted_words)

        if self.config.normalize_spaces:
            result = re.sub(r'\s+', ' ', result)

        if self.config.remove_line_hyphens:
            # Remove hifens de quebra de linha: "word- \nbreaking" -> "wordbreaking"
            result = re.sub(r'(\w)-\s+(\w)', r'\1\2', result)

        return result.strip()

    def reconstruct_lines(
        self,
        words: List[SpatialWord],
        tolerance_y: Optional[float] = None
    ) -> List[SpatialLine]:
        """
        Reconstrói linhas a partir de palavras reordenadas.

        Usa detecção de overlap vertical para agrupar elementos que estão
        na mesma linha visual, mesmo com pequenas diferenças de Y
        (como bullets/checkboxes desalinhados do texto).

        Args:
            words: Lista de palavras
            tolerance_y: Tolerância vertical

        Returns:
            Lista de SpatialLine
        """
        if not words:
            return []

        tolerance = tolerance_y or self.config.vertical_tolerance

        # Ordenar palavras por Y primeiro, depois por X
        sorted_words = sorted(words, key=lambda w: (w.y0, w.x0))

        # Agrupar usando overlap vertical
        lines: List[SpatialLine] = []
        current_line: List[SpatialWord] = []
        current_y_min = 0.0
        current_y_max = 0.0

        for word in sorted_words:
            if not current_line:
                # Primeira palavra da linha
                current_line.append(word)
                current_y_min = word.y0
                current_y_max = word.y1
            else:
                # Verificar se a palavra pertence à linha atual
                # Critérios: overlap vertical OU diferença de Y dentro da tolerância
                word_overlaps = (word.y0 <= current_y_max + tolerance and
                                 word.y1 >= current_y_min - tolerance)
                y_diff_ok = abs(word.y0 - current_y_min) <= tolerance * 2

                if word_overlaps or y_diff_ok:
                    # Adiciona à linha atual
                    current_line.append(word)
                    current_y_min = min(current_y_min, word.y0)
                    current_y_max = max(current_y_max, word.y1)
                else:
                    # Nova linha - finaliza a atual
                    line_words = sorted(current_line, key=lambda w: w.x0)
                    lines.append(SpatialLine(words=line_words, y_group=len(lines)))

                    # Inicia nova linha
                    current_line = [word]
                    current_y_min = word.y0
                    current_y_max = word.y1

        # Finalizar última linha
        if current_line:
            line_words = sorted(current_line, key=lambda w: w.x0)
            lines.append(SpatialLine(words=line_words, y_group=len(lines)))

        # Pós-processamento: mesclar linhas que contêm apenas bullet/checkbox
        # com a linha de texto adjacente (se o bullet estiver antes do texto)
        lines = self._merge_bullet_lines(lines, tolerance)

        self._stats['lines_reconstructed'] += len(lines)

        return lines

    def _merge_bullet_lines(
        self,
        lines: List[SpatialLine],
        tolerance: float
    ) -> List[SpatialLine]:
        """
        Mescla linhas que contêm apenas bullets/checkboxes com texto adjacente.

        Isso resolve o problema de checkboxes desalinhados verticalmente.
        """
        if len(lines) <= 1:
            return lines

        # Caracteres que são bullets/checkboxes
        bullet_chars = {
            '\uf0fc', '\uf0b7', '\uf0a7', '\uf076', '\uf077', '\uf0fe',
            '•', '◦', '○', '●', '■', '□', '▪', '▫', '‣', '⁃',
            '✓', '✗', '✔', '✘', '☐', '☑', '☒',
            '-', '–', '—', '−', '*',
        }

        result = []
        i = 0

        while i < len(lines):
            current_line = lines[i]

            # Verificar se a linha é apenas um bullet/checkbox
            is_bullet_only = (
                len(current_line.words) == 1 and
                len(current_line.words[0].text.strip()) <= 2 and
                any(c in current_line.words[0].text for c in bullet_chars)
            )

            if is_bullet_only and i + 1 < len(lines):
                next_line = lines[i + 1]

                # Verificar se as linhas estão próximas verticalmente
                current_y = current_line.bbox[1]
                next_y = next_line.bbox[1]
                y_diff = abs(next_y - current_y)

                # Se próximas (tolerância mais generosa para bullets)
                if y_diff <= tolerance * 3:
                    # Mesclar: bullet + conteúdo da próxima linha
                    merged_words = current_line.words + next_line.words
                    merged_words = sorted(merged_words, key=lambda w: w.x0)
                    result.append(SpatialLine(words=merged_words, y_group=len(result)))
                    i += 2  # Pular a próxima linha pois foi mesclada
                    continue

            result.append(current_line)
            i += 1

        return result

    def extract_formula_area(
        self,
        page,
        bbox: Tuple[float, float, float, float],
        tolerance_y: Optional[float] = None
    ) -> str:
        """
        Extrai e reconstrói texto de uma área de fórmula.

        Este é o método principal para resolver "PDF Spaghetti" em fórmulas:
        1. Extrai palavras da área especificada
        2. Reordena espacialmente
        3. Reconstrói o texto

        Args:
            page: Objeto fitz.Page
            bbox: Área da fórmula (x0, y0, x1, y1)
            tolerance_y: Tolerância vertical

        Returns:
            Texto reconstruído da fórmula
        """
        words = self.extract_words_from_bbox(page, bbox)
        return self.reconstruct_text(words, tolerance_y)

    def process_page(
        self,
        page,
        math_zones: Optional[List[Tuple[float, float, float, float]]] = None
    ) -> Dict[str, any]:
        """
        Processa uma página completa.

        Args:
            page: Objeto fitz.Page
            math_zones: Lista opcional de áreas de fórmulas (bboxes)

        Returns:
            Dicionário com:
            - 'full_text': Texto completo reordenado
            - 'lines': Lista de SpatialLine
            - 'math_texts': Lista de textos das zonas matemáticas
        """
        self._stats['pages_processed'] += 1

        all_words = self.extract_words_from_page(page)

        result = {
            'full_text': self.reconstruct_text(all_words),
            'lines': self.reconstruct_lines(all_words),
            'math_texts': [],
        }

        # Processar zonas matemáticas se fornecidas
        if math_zones:
            for bbox in math_zones:
                math_text = self.extract_formula_area(page, bbox)
                result['math_texts'].append({
                    'bbox': bbox,
                    'text': math_text,
                })

        return result

    def get_stats(self) -> Dict:
        """Retorna estatísticas de processamento."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'words_extracted': 0,
            'lines_reconstructed': 0,
            'pages_processed': 0,
        }


def get_spatial_extractor(config: Optional[SpatialExtractorConfig] = None) -> SpatialExtractor:
    """Factory function para obter instância do extrator."""
    return SpatialExtractor(config)


def reorder_formula_text(
    page,
    bbox: Tuple[float, float, float, float],
    tolerance_y: float = 3.0
) -> str:
    """
    Função utilitária para reordenar texto de uma área de fórmula.

    Uso direto sem precisar instanciar a classe.

    Args:
        page: Objeto fitz.Page
        bbox: Área da fórmula
        tolerance_y: Tolerância vertical

    Returns:
        Texto reordenado
    """
    config = SpatialExtractorConfig(vertical_tolerance=tolerance_y)
    extractor = SpatialExtractor(config)
    return extractor.extract_formula_area(page, bbox, tolerance_y)


def smart_reorder_with_subscripts(
    words: List[SpatialWord],
    base_tolerance: float = 3.0
) -> str:
    """
    Reordena palavras com tratamento especial para sub/superscritos.

    Detecta automaticamente elementos que são sub/superscritos
    (menores e deslocados verticalmente) e os formata apropriadamente.

    Args:
        words: Lista de palavras
        base_tolerance: Tolerância base para agrupamento

    Returns:
        Texto reconstruído com marcações de sub/superscrito
    """
    if not words:
        return ""

    # Calcular tamanho médio de fonte
    avg_size = sum(w.font_size for w in words) / len(words)

    # Ordenar espacialmente
    extractor = SpatialExtractor()
    sorted_words = extractor.reorder_spatially(words, base_tolerance)

    result_parts = []

    for i, word in enumerate(sorted_words):
        text = word.text

        # Detectar subscrito (fonte menor e abaixo da linha base média)
        if word.font_size < avg_size * 0.8:
            # Verificar posição relativa à palavra anterior
            if i > 0:
                prev_word = sorted_words[i - 1]
                y_diff = word.y0 - prev_word.y0

                if y_diff > avg_size * 0.2:  # Abaixo = subscrito
                    text = f"_{{{text}}}"
                elif y_diff < -avg_size * 0.2:  # Acima = superscrito
                    text = f"^{{{text}}}"

        result_parts.append(text)

    return " ".join(result_parts)


def extract_with_coordinates(page) -> List[Dict]:
    """
    Extrai texto com coordenadas completas para análise.

    Retorna formato compatível com outros módulos do sistema.

    Args:
        page: Objeto fitz.Page

    Returns:
        Lista de dicionários com 'text', 'bbox', 'font_size', etc.
    """
    extractor = SpatialExtractor()
    words = extractor.extract_words_from_page(page)

    return [
        {
            'text': w.text,
            'bbox': (w.x0, w.y0, w.x1, w.y1),
            'font_size': w.font_size,
            'font_name': w.font_name,
            'flags': w.flags,
            'x0': w.x0,
            'y0': w.y0,
            'x1': w.x1,
            'y1': w.y1,
        }
        for w in words
    ]
