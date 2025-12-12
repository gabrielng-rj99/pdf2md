"""
Módulo de detecção e classificação de headings baseado em tamanho de fonte.

Este módulo implementa um sistema inteligente para identificar e hierarquizar
headings em documentos PDF convertidos para Markdown, usando apenas o tamanho
da fonte como métrica principal.

Características:
- Detecção automática de níveis de heading (H1-H6) por tamanho de fonte
- Filtragem de textos repetidos e genéricos
- Remoção de headings em rodapés/cabeçalhos
- Normalização e limpeza de texto
- Validação robusta de entrada
"""

import logging
import re
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class HeadingCandidate:
    """Representa um candidato a heading com metadados."""
    text: str
    font_size: float
    page_num: int
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    y_ratio: float  # Posição vertical como razão (0.0-1.0)


@dataclass
class Heading:
    """Representa um heading validado."""
    text: str
    level: int  # 1-6
    page_num: int
    font_size: float
    position: Tuple[float, float, float, float]


class HeadingFilter:
    """
    Filtra e classifica headings de um documento PDF com base em tamanho de fonte.

    O algoritmo funciona em etapas:
    1. Coleta todos os candidatos a heading com tamanho de fonte
    2. Remove duplicatas e textos repetidos entre páginas
    3. Filtra rodapés/cabeçalhos e textos genéricos
    4. Mapeia tamanhos únicos para níveis H1-H6
    5. Valida e retorna headings estruturados
    """

    # Palavras genéricas que geralmente não são títulos principais
    GENERIC_TITLES = {
        "sumário", "índice", "table of contents",
        "introdução", "introduction",
        "conclusão", "conclusion",
        "referências", "references",
        "apêndice", "appendix",
        "prefácio", "preface",
        "agradecimentos", "acknowledgments",
        "prólogo", "prologue",
        "nota", "notes",
        "observação", "observations",
    }

    # Limites de tamanho de fonte para validação
    MIN_FONT_SIZE = 10.0  # Muito pequeno para ser heading
    MAX_FONT_SIZE = 72.0  # Limite superior razoável

    # Margem de tolerância para agrupar tamanhos similares (em pontos)
    FONT_SIZE_TOLERANCE = 0.5

    # Limites para detecção de rodapé/cabeçalho (como razão da altura da página)
    HEADER_THRESHOLD = 0.05  # Top 5%
    FOOTER_THRESHOLD = 0.92  # Bottom 8%

    def __init__(self, page_height: float = 792.0):
        """
        Inicializa o filtro de headings.

        Args:
            page_height: Altura padrão da página em pontos (padrão: 792pt = 11 polegadas)
        """
        self.page_height = page_height
        self.size_to_level: Dict[float, int] = {}
        self.seen_texts: Set[str] = set()
        self.logger = logger

    def reset(self) -> None:
        """Reseta o estado interno do filtro."""
        self.size_to_level = {}
        self.seen_texts = set()

    def add_candidate(self, candidates: List[HeadingCandidate]) -> None:
        """
        Processa uma lista de candidatos a heading.

        Args:
            candidates: Lista de HeadingCandidate com texto e tamanho de fonte

        Raises:
            ValueError: Se a lista for inválida (não é lista de HeadingCandidate)
        """
        if not candidates:
            return  # Lista vazia é válida, apenas retorna sem processar

        if not all(isinstance(c, HeadingCandidate) for c in candidates):
            raise ValueError("Todos os candidatos devem ser instâncias de HeadingCandidate")

        # Validar candidatos
        valid_candidates = self._validate_candidates(candidates)

        if not valid_candidates:
            self.logger.warning("Nenhum candidato válido após validação")
            return

        # Mapear tamanhos para níveis
        self._build_size_to_level_mapping(valid_candidates)

    def _validate_candidates(self, candidates: List[HeadingCandidate]) -> List[HeadingCandidate]:
        """
        Valida e filtra candidatos a heading.

        Aplica filtros para:
        - Tamanho de fonte fora do intervalo válido
        - Texto vazio ou muito curto
        - Títulos genéricos
        - Posição em rodapé/cabeçalho
        - Duplicatas (mesmo texto em múltiplas páginas)

        Args:
            candidates: Lista de candidatos brutos

        Returns:
            Lista de candidatos válidos
        """
        valid = []

        for candidate in candidates:
            # Filtro 1: Tamanho de fonte válido
            if not (self.MIN_FONT_SIZE <= candidate.font_size <= self.MAX_FONT_SIZE):
                self.logger.debug(
                    f"Candidato rejeitado (tamanho inválido): '{candidate.text}' "
                    f"({candidate.font_size}pt)"
                )
                continue

            # Filtro 2: Texto válido
            if not self._is_valid_text(candidate.text):
                self.logger.debug(f"Candidato rejeitado (texto inválido): '{candidate.text}'")
                continue

            # Filtro 3: Não é título genérico
            if self._is_generic_title(candidate.text):
                self.logger.debug(f"Candidato rejeitado (genérico): '{candidate.text}'")
                continue

            # Filtro 4: Não está em rodapé/cabeçalho
            if self._is_in_margin(candidate.y_ratio):
                self.logger.debug(
                    f"Candidato rejeitado (margem): '{candidate.text}' "
                    f"(y_ratio={candidate.y_ratio:.2f})"
                )
                continue

            # Filtro 5: Não é duplicata
            normalized_text = self._normalize_text(candidate.text)
            if normalized_text in self.seen_texts:
                self.logger.debug(f"Candidato rejeitado (duplicata): '{candidate.text}'")
                continue

            self.seen_texts.add(normalized_text)
            valid.append(candidate)

        self.logger.info(f"Validação: {len(candidates)} candidatos → {len(valid)} válidos")
        return valid

    def _is_valid_text(self, text: str) -> bool:
        """
        Valida se o texto é apropriado para ser heading.

        Args:
            text: Texto a validar

        Returns:
            True se válido, False caso contrário
        """
        if not text or not text.strip():
            return False

        # Mínimo de 2 caracteres
        if len(text.strip()) < 2:
            return False

        # Máximo de 200 caracteres (headings muito longos são raros)
        if len(text.strip()) > 200:
            return False

        # Não deve ser apenas números ou caracteres especiais
        if not re.search(r"[a-záéíóúàâãñ]", text.lower()):
            return False

        return True

    def _is_generic_title(self, text: str) -> bool:
        """
        Verifica se o texto é um título genérico comum.

        Args:
            text: Texto a verificar

        Returns:
            True se genérico, False caso contrário
        """
        normalized = self._normalize_text(text).lower()
        return normalized in self.GENERIC_TITLES

    def _is_in_margin(self, y_ratio: float) -> bool:
        """
        Verifica se a posição vertical está em rodapé ou cabeçalho.

        Args:
            y_ratio: Posição vertical como razão (0.0-1.0)

        Returns:
            True se em margem, False caso contrário
        """
        return y_ratio < self.HEADER_THRESHOLD or y_ratio > self.FOOTER_THRESHOLD

    def _normalize_text(self, text: str) -> str:
        """
        Normaliza texto para comparação.

        Remove espaços extras, convert para minúsculas, etc.

        Args:
            text: Texto a normalizar

        Returns:
            Texto normalizado
        """
        return re.sub(r"\s+", " ", text.strip()).lower()

    def _build_size_to_level_mapping(self, candidates: List[HeadingCandidate]) -> None:
        """
        Constrói o mapeamento de tamanho de fonte para nível de heading.

        Agrupa tamanhos similares e mapeia para H1-H6 em ordem descendente.

        Args:
            candidates: Lista de candidatos válidos
        """
        if not candidates:
            return

        # Agrupar tamanhos similares
        sizes = self._group_similar_sizes([c.font_size for c in candidates])

        # Ordenar descendente (maior → H1)
        sizes.sort(reverse=True)

        # Mapear para níveis (máximo H6)
        self.size_to_level = {}
        for idx, size in enumerate(sizes[:6]):
            level = idx + 1
            self.size_to_level[size] = level
            self.logger.info(f"Tamanho {size:.1f}pt → H{level}")

        if len(sizes) > 6:
            self.logger.warning(f"PDF tem {len(sizes)} níveis de tamanho; "
                              f"os menores serão agrupados em H6")

    def _group_similar_sizes(self, sizes: List[float]) -> List[float]:
        """
        Agrupa tamanhos de fonte similares (dentro da tolerância).

        Reduz ruído causado por pequenas variações de tamanho no PDF.

        Args:
            sizes: Lista de tamanhos de fonte

        Returns:
            Lista de tamanhos agrupados (sem duplicatas próximas)
        """
        if not sizes:
            return []

        sizes = sorted(set(sizes), reverse=True)
        grouped = []

        for size in sizes:
            # Verifica se há um tamanho similar já agrupado
            if not any(abs(size - g) <= self.FONT_SIZE_TOLERANCE for g in grouped):
                grouped.append(size)

        return grouped

    def get_heading_level(self, font_size: float) -> Optional[int]:
        """
        Retorna o nível de heading para um tamanho de fonte.

        Args:
            font_size: Tamanho da fonte em pontos

        Returns:
            Nível de heading (1-6) ou None se não for heading
        """
        # Buscar o tamanho mapeado mais próximo
        for size, level in self.size_to_level.items():
            if abs(font_size - size) <= self.FONT_SIZE_TOLERANCE:
                return level

        return None

    def filter_headings(self, candidates: List[HeadingCandidate]) -> List[Heading]:
        """
        Filtra uma lista de candidatos e retorna headings validados.

        Esta é a função principal do módulo.

        Args:
            candidates: Lista de HeadingCandidate brutos

        Returns:
            Lista de Heading validados e classificados
        """
        if not candidates:
            return []

        self.reset()
        self.add_candidate(candidates)

        if not self.size_to_level:
            self.logger.warning("Nenhum mapeamento de tamanho disponível")
            return []

        headings = []
        for candidate in candidates:
            # Reaplicar filtros de validade
            if not self._is_valid_text(candidate.text):
                continue
            if self._is_generic_title(candidate.text):
                continue
            if self._is_in_margin(candidate.y_ratio):
                continue

            # Duplicatas: apenas primeira ocorrência
            normalized = self._normalize_text(candidate.text)
            if normalized in [self._normalize_text(h.text) for h in headings]:
                continue

            # Obter nível
            level = self.get_heading_level(candidate.font_size)
            if level is None:
                continue

            heading = Heading(
                text=candidate.text.strip(),
                level=level,
                page_num=candidate.page_num,
                font_size=candidate.font_size,
                position=candidate.bbox,
            )
            headings.append(heading)

        self.logger.info(f"Total de headings filtrados: {len(headings)}")
        return headings

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas sobre o mapeamento de headings.

        Returns:
            Dicionário com estatísticas
        """
        return {
            "total_sizes": len(self.size_to_level),
            "size_to_level": self.size_to_level,
            "total_seen_texts": len(self.seen_texts),
            "page_height": self.page_height,
        }
