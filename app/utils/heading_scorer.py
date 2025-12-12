"""
Sistema Inteligente de Pontuação para Classificação de Headings.

Este módulo implementa um sistema de scoring multi-critério para distinguir
headings de corpo de texto em documentos PDF, sem uso de ML pesado ou APIs externas.

Características:
- Sistema de pontuação baseado em múltiplas heurísticas
- Análise estatística de frequência de tamanhos de fonte
- Detecção de padrões estruturais (seções numeradas, bullets, etc)
- Análise de contexto (sequência de elementos)
- Configurável e extensível
- Benchmark integrado para otimização

Autor: Gerado para projeto pdf2md
"""

import re
import time
import logging
from typing import List, Dict, Tuple, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from collections import Counter
from enum import Enum
from functools import lru_cache

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTES E CONFIGURAÇÃO
# =============================================================================

# Stopwords em português (comuns em parágrafos, raras em headings)
STOPWORDS_PT: Set[str] = {
    'de', 'da', 'do', 'das', 'dos', 'a', 'o', 'as', 'os', 'e', 'é',
    'em', 'no', 'na', 'nos', 'nas', 'um', 'uma', 'uns', 'umas',
    'que', 'para', 'por', 'com', 'não', 'se', 'ao', 'aos', 'ou',
    'seu', 'sua', 'seus', 'suas', 'são', 'mais', 'como', 'mas',
    'foi', 'ser', 'tem', 'já', 'está', 'isso', 'isto', 'esse',
    'essa', 'este', 'esta', 'pelo', 'pela', 'pelos', 'pelas',
    'entre', 'depois', 'sobre', 'mesmo', 'quando', 'muito',
    'também', 'pode', 'assim', 'qual', 'só', 'bem', 'sem',
    'ele', 'ela', 'eles', 'elas', 'nos', 'me', 'lhe', 'lo', 'la',
}

# Stopwords em inglês (para documentos bilíngues)
STOPWORDS_EN: Set[str] = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
    'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'must',
    'that', 'which', 'who', 'whom', 'this', 'these', 'those',
    'it', 'its', 'as', 'if', 'than', 'so', 'such', 'no', 'not',
}

ALL_STOPWORDS = STOPWORDS_PT | STOPWORDS_EN


class ScoringStrategy(Enum):
    """Estratégias de scoring disponíveis."""
    FAST = "fast"           # Apenas heurísticas básicas (mais rápido)
    BALANCED = "balanced"   # Heurísticas + análise estatística
    ACCURATE = "accurate"   # Todas as análises (mais preciso)


@dataclass
class ScoringConfig:
    """Configuração do sistema de scoring."""
    # Thresholds
    heading_threshold: int = 4          # Score mínimo para ser heading (aumentado)
    max_heading_length: int = 120       # Comprimento máximo de heading
    min_heading_length: int = 3         # Comprimento mínimo de heading (aumentado)
    min_word_count: int = 1             # Mínimo de palavras para ser heading

    # Tolerâncias
    font_size_tolerance: float = 0.5    # Tolerância para agrupar tamanhos
    body_size_margin: float = 1.5       # Margem acima do corpo para ser heading

    # Pesos (podem ser ajustados)
    weight_section_pattern: int = 5     # Padrão de seção numerada
    weight_chapter_keyword: int = 4     # Palavras como "Capítulo", "Seção"
    weight_bold: int = 3                # Texto em negrito
    weight_larger_than_body: int = 2    # Maior que corpo de texto
    weight_starts_upper: int = 1        # Começa com maiúscula

    penalty_too_long: int = -5          # Texto muito longo
    penalty_ends_period: int = -3       # Termina com ponto
    penalty_bullet: int = -4            # É bullet point
    penalty_same_as_body: int = -3      # Mesmo tamanho do corpo
    penalty_sequence: int = -2          # Sequência do mesmo tamanho
    penalty_high_stopwords: int = -2    # Muitas stopwords
    penalty_lowercase_start: int = -1   # Começa com minúscula

    # Stopword threshold
    stopword_ratio_threshold: float = 0.35

    # Filtros adicionais
    filter_repeated_headers: bool = True    # Filtra headers repetidos (HSN002, etc)
    filter_numbers_only: bool = True        # Filtra textos só com números
    filter_punctuation_only: bool = True    # Filtra textos só com pontuação

    # Estratégia
    strategy: ScoringStrategy = ScoringStrategy.BALANCED


@dataclass
class ScoringContext:
    """Contexto para scoring de um candidato."""
    body_font_size: float               # Tamanho mais comum (corpo)
    body_font_sizes: Set[float] = field(default_factory=set)  # Tamanhos de corpo
    prev_font_size: Optional[float] = None
    next_font_size: Optional[float] = None
    prev_is_heading: bool = False
    total_candidates: int = 0
    position_in_page: float = 0.5       # 0.0 = topo, 1.0 = base


@dataclass
class HeadingCandidate:
    """Candidato a heading com todos os metadados."""
    text: str
    font_size: float
    page_num: int
    bbox: Tuple[float, float, float, float]
    y_ratio: float
    is_bold: bool = False
    is_italic: bool = False
    font_name: str = ""
    flags: int = 0


@dataclass
class ScoringResult:
    """Resultado do scoring de um candidato."""
    candidate: HeadingCandidate
    score: int
    is_heading: bool
    level: int                          # 1-6 se for heading, 0 se não for
    reasons: List[str] = field(default_factory=list)
    computation_time_us: float = 0      # Tempo em microsegundos


@dataclass
class BenchmarkResult:
    """Resultado de benchmark de uma estratégia."""
    strategy: ScoringStrategy
    total_time_ms: float
    avg_time_per_candidate_us: float
    candidates_processed: int
    headings_detected: int
    precision_estimate: float           # Estimativa baseada em heurísticas
    memory_estimate_kb: float


# =============================================================================
# PADRÕES REGEX (PRÉ-COMPILADOS PARA PERFORMANCE)
# =============================================================================

# Padrões de seção numerada (muito forte indicador de heading)
SECTION_PATTERNS = [
    re.compile(r'^\d+(\.\d+)*\s*[-–—:]?\s+\w', re.IGNORECASE),      # "1.2 - Título"
    re.compile(r'^\d+(\.\d+)*\s*[-–—]?\s*$'),                        # "1.2" sozinho
    re.compile(r'^[IVXLCDM]+(\.[IVXLCDM]+)*\s*[-–—:]?\s+\w', re.I), # Romanos "II.3"
]

# Palavras-chave de seção (forte indicador)
CHAPTER_KEYWORDS = re.compile(
    r'^(cap[íi]tulo|se[çc][ãa]o|parte|anexo|ap[êe]ndice|'
    r'chapter|section|part|appendix|annex)\s+',
    re.IGNORECASE
)

# Palavras-chave de conteúdo estrutural
STRUCTURAL_KEYWORDS = re.compile(
    r'^(introdu[çc][ãa]o|conclus[ãa]o|resumo|abstract|'
    r'objetivos?|m[ée]todos?|resultados?|discuss[ãa]o|'
    r'refer[êe]ncias?|bibliografia|agradecimentos?|'
    r'sum[áa]rio|[íi]ndice|gloss[áa]rio|prefácio|'
    r'introduction|conclusion|summary|methods?|results?|'
    r'discussion|references?|acknowledgments?)\s*$',
    re.IGNORECASE
)

# Padrões de bullet/lista (NÃO é heading)
BULLET_PATTERNS = [
    re.compile(r'^[-•*▪▸►◦‣⁃]\s+'),              # Bullets simples
    re.compile(r'^\(?[a-z]\)\s+', re.IGNORECASE), # (a), a)
    re.compile(r'^\d+[.)]\s+'),                    # 1. ou 1)
    re.compile(r'^[ivxlcdm]+[.)]\s+', re.I),      # i. ii. iii.
]

# Padrão de continuação de frase (indica corpo, não heading)
CONTINUATION_PATTERN = re.compile(r'^[a-záéíóúàâãõç]', re.IGNORECASE)

# Padrão de fórmula/equação (geralmente não é heading)
FORMULA_PATTERN = re.compile(r'[=+\-*/^∑∏∫√].*[=+\-*/^∑∏∫√]|^\s*\(.+\)\s*$')

# Padrão de texto que é só números ou pontuação
NUMBERS_ONLY_PATTERN = re.compile(r'^[\d\s.,;:]+$')
PUNCTUATION_ONLY_PATTERN = re.compile(r'^[\s.,;:!?\-–—()\[\]{}]+$')

# Padrão de códigos repetitivos (headers de página como HSN002)
REPETITIVE_CODE_PATTERN = re.compile(r'^[A-Z]{2,5}\d{2,5}$')


# =============================================================================
# FUNÇÕES AUXILIARES OTIMIZADAS
# =============================================================================

@lru_cache(maxsize=10000)
def calculate_stopword_ratio(text: str) -> float:
    """
    Calcula a proporção de stopwords no texto.
    Usa cache LRU para textos repetidos.

    Args:
        text: Texto a analisar

    Returns:
        Proporção de stopwords (0.0 a 1.0)
    """
    words = text.lower().split()
    if not words:
        return 0.0

    stopword_count = sum(1 for w in words if w in ALL_STOPWORDS)
    return stopword_count / len(words)


@lru_cache(maxsize=1000)
def has_section_pattern(text: str) -> bool:
    """Verifica se texto tem padrão de seção numerada."""
    return any(p.match(text) for p in SECTION_PATTERNS)


@lru_cache(maxsize=1000)
def has_chapter_keyword(text: str) -> bool:
    """Verifica se texto tem palavra-chave de capítulo/seção."""
    return bool(CHAPTER_KEYWORDS.match(text))


@lru_cache(maxsize=1000)
def has_structural_keyword(text: str) -> bool:
    """Verifica se texto é palavra estrutural (Introdução, Conclusão, etc)."""
    return bool(STRUCTURAL_KEYWORDS.match(text.strip()))


@lru_cache(maxsize=1000)
def is_bullet_item(text: str) -> bool:
    """Verifica se texto é item de lista/bullet."""
    return any(p.match(text) for p in BULLET_PATTERNS)


@lru_cache(maxsize=1000)
def looks_like_formula(text: str) -> bool:
    """Verifica se texto parece fórmula matemática."""
    return bool(FORMULA_PATTERN.search(text))


@lru_cache(maxsize=1000)
def is_numbers_only(text: str) -> bool:
    """Verifica se texto contém apenas números e pontuação."""
    return bool(NUMBERS_ONLY_PATTERN.match(text.strip()))


@lru_cache(maxsize=1000)
def is_punctuation_only(text: str) -> bool:
    """Verifica se texto contém apenas pontuação."""
    return bool(PUNCTUATION_ONLY_PATTERN.match(text.strip()))


@lru_cache(maxsize=1000)
def is_repetitive_code(text: str) -> bool:
    """Verifica se texto é código repetitivo de header (ex: HSN002)."""
    return bool(REPETITIVE_CODE_PATTERN.match(text.strip()))


def is_valid_heading_text(text: str, min_length: int = 3, min_words: int = 1) -> bool:
    """
    Verifica se o texto é válido para ser um heading.

    Args:
        text: Texto a validar
        min_length: Comprimento mínimo
        min_words: Número mínimo de palavras

    Returns:
        True se válido, False caso contrário
    """
    text = text.strip()

    # Muito curto
    if len(text) < min_length:
        return False

    # Só números
    if is_numbers_only(text):
        return False

    # Só pontuação
    if is_punctuation_only(text):
        return False

    # Código repetitivo
    if is_repetitive_code(text):
        return False

    # Precisa ter pelo menos uma letra
    if not any(c.isalpha() for c in text):
        return False

    # Verifica número mínimo de palavras
    words = [w for w in text.split() if any(c.isalpha() for c in w)]
    if len(words) < min_words:
        return False

    return True


def extract_flags(flags: int) -> Tuple[bool, bool]:
    """
    Extrai informações de bold/italic das flags do PyMuPDF.

    PyMuPDF flags:
    - 1 (2^0): superscript
    - 2 (2^1): italic
    - 4 (2^2): serifed
    - 8 (2^3): monospaced
    - 16 (2^4): bold

    Args:
        flags: Flags do span

    Returns:
        Tupla (is_bold, is_italic)
    """
    is_bold = bool(flags & 16)
    is_italic = bool(flags & 2)
    return is_bold, is_italic


# =============================================================================
# CLASSE PRINCIPAL: HeadingScorer
# =============================================================================

class HeadingScorer:
    """
    Sistema de pontuação inteligente para classificação de headings.

    Implementa múltiplas estratégias de scoring com diferentes trade-offs
    entre velocidade e precisão.
    """

    def __init__(self, config: Optional[ScoringConfig] = None):
        """
        Inicializa o scorer.

        Args:
            config: Configuração do sistema (usa padrão se None)
        """
        self.config = config or ScoringConfig()
        self.context: Optional[ScoringContext] = None
        self._body_size_cache: Optional[float] = None
        self._size_to_level: Dict[float, int] = {}
        self._benchmark_results: List[BenchmarkResult] = []

        logger.info(f"HeadingScorer inicializado com estratégia: {self.config.strategy.value}")

    def analyze_candidates(self, candidates: List[HeadingCandidate]) -> None:
        """
        Analisa candidatos para construir contexto estatístico.

        Esta função DEVE ser chamada antes de score_candidate para
        estabelecer o tamanho de corpo de texto e outros contextos.

        Args:
            candidates: Lista de todos os candidatos
        """
        if not candidates:
            logger.warning("Lista de candidatos vazia")
            return

        # Análise de frequência de tamanhos
        size_counter = Counter()
        for c in candidates:
            # Agrupa tamanhos similares
            rounded_size = round(c.font_size * 2) / 2  # Arredonda para 0.5
            size_counter[rounded_size] += 1

        # O tamanho mais frequente é o corpo de texto
        if size_counter:
            body_size = size_counter.most_common(1)[0][0]

            # Identifica tamanhos que são "corpo" (top 2 mais frequentes com >10% cada)
            total = sum(size_counter.values())
            body_sizes = set()
            for size, count in size_counter.most_common(3):
                if count / total > 0.08:  # Pelo menos 8% das ocorrências
                    body_sizes.add(size)
        else:
            body_size = 12.0
            body_sizes = {12.0}

        self._body_size_cache = body_size

        # Cria contexto
        self.context = ScoringContext(
            body_font_size=body_size,
            body_font_sizes=body_sizes,
            total_candidates=len(candidates)
        )

        # Constrói mapeamento de tamanho para nível
        self._build_size_to_level_mapping(candidates)

        logger.info(f"Análise concluída: body_size={body_size:.1f}pt, "
                   f"body_sizes={sorted(body_sizes)}, "
                   f"total_candidates={len(candidates)}")

    def _build_size_to_level_mapping(self, candidates: List[HeadingCandidate]) -> None:
        """
        Constrói mapeamento de tamanho de fonte para nível de heading.

        Considera apenas tamanhos que têm chance de ser heading
        (maiores que corpo ou bold).
        """
        # Coleta tamanhos únicos de possíveis headings
        potential_heading_sizes = set()

        for c in candidates:
            # Só considera se maior que corpo ou bold
            if self.context is not None and (c.font_size > self.context.body_font_size + self.config.body_size_margin or
                c.is_bold):
                potential_heading_sizes.add(round(c.font_size * 2) / 2)

        # Remove tamanhos de corpo
        if self.context is not None:
            potential_heading_sizes -= self.context.body_font_sizes

        # Ordena decrescente e mapeia para níveis
        sorted_sizes = sorted(potential_heading_sizes, reverse=True)

        self._size_to_level = {}
        for idx, size in enumerate(sorted_sizes[:6]):  # Máximo H6
            self._size_to_level[size] = idx + 1

        logger.debug(f"Size to level mapping: {self._size_to_level}")

    def score_candidate(
        self,
        candidate: HeadingCandidate,
        prev_candidate: Optional[HeadingCandidate] = None,
        next_candidate: Optional[HeadingCandidate] = None
    ) -> ScoringResult:
        """
        Calcula score de um candidato para determinar se é heading.

        Args:
            candidate: Candidato a avaliar
            prev_candidate: Candidato anterior (para contexto)
            next_candidate: Candidato seguinte (para contexto)

        Returns:
            ScoringResult com score, decisão e razões
        """
        start_time = time.perf_counter()

        if self.context is None:
            raise RuntimeError("Contexto não inicializado. Chame analyze_candidates primeiro.")

        text = candidate.text.strip()

        # Validação prévia rápida - rejeita textos inválidos
        if not is_valid_heading_text(text, self.config.min_heading_length, self.config.min_word_count):
            elapsed_us = (time.perf_counter() - start_time) * 1_000_000
            return ScoringResult(
                candidate=candidate,
                score=-10,
                is_heading=False,
                level=0,
                reasons=["texto inválido (muito curto, só números, ou código repetitivo)"],
                computation_time_us=elapsed_us
            )

        # Atualiza contexto com vizinhos
        ctx = ScoringContext(
            body_font_size=self.context.body_font_size,
            body_font_sizes=self.context.body_font_sizes,
            prev_font_size=prev_candidate.font_size if prev_candidate else None,
            next_font_size=next_candidate.font_size if next_candidate else None,
            total_candidates=self.context.total_candidates,
            position_in_page=candidate.y_ratio
        )

        # Seleciona estratégia
        if self.config.strategy == ScoringStrategy.FAST:
            score, reasons = self._score_fast(candidate, ctx)
        elif self.config.strategy == ScoringStrategy.BALANCED:
            score, reasons = self._score_balanced(candidate, ctx)
        else:  # ACCURATE
            score, reasons = self._score_accurate(candidate, ctx)

        # Determina se é heading e qual nível
        is_heading = score >= self.config.heading_threshold
        level = self._determine_level(candidate, is_heading)

        elapsed_us = (time.perf_counter() - start_time) * 1_000_000

        return ScoringResult(
            candidate=candidate,
            score=score,
            is_heading=is_heading,
            level=level,
            reasons=reasons,
            computation_time_us=elapsed_us
        )

    def _score_fast(
        self,
        candidate: HeadingCandidate,
        ctx: ScoringContext
    ) -> Tuple[int, List[str]]:
        """
        Estratégia FAST: apenas heurísticas básicas.
        Tempo alvo: < 1µs por candidato.
        """
        score = 0
        reasons = []
        text = candidate.text.strip()

        # === SINAIS POSITIVOS ===

        # Padrão de seção numerada (muito forte)
        if has_section_pattern(text):
            score += self.config.weight_section_pattern
            reasons.append(f"+{self.config.weight_section_pattern}: padrão seção")

        # Bold
        if candidate.is_bold:
            score += self.config.weight_bold
            reasons.append(f"+{self.config.weight_bold}: bold")

        # Maior que corpo
        size_diff = candidate.font_size - ctx.body_font_size
        if size_diff > self.config.body_size_margin:
            score += self.config.weight_larger_than_body
            reasons.append(f"+{self.config.weight_larger_than_body}: maior que corpo")

        # === SINAIS NEGATIVOS ===

        # Muito longo
        if len(text) > self.config.max_heading_length:
            score += self.config.penalty_too_long
            reasons.append(f"{self.config.penalty_too_long}: muito longo")

        # Termina com ponto
        if text.endswith('.'):
            score += self.config.penalty_ends_period
            reasons.append(f"{self.config.penalty_ends_period}: termina com ponto")

        # É bullet
        if is_bullet_item(text):
            score += self.config.penalty_bullet
            reasons.append(f"{self.config.penalty_bullet}: bullet")

        return score, reasons

    def _score_balanced(
        self,
        candidate: HeadingCandidate,
        ctx: ScoringContext
    ) -> Tuple[int, List[str]]:
        """
        Estratégia BALANCED: heurísticas + análise estatística.
        Tempo alvo: < 5µs por candidato.
        """
        # Começa com score da estratégia fast
        score, reasons = self._score_fast(candidate, ctx)
        text = candidate.text.strip()

        # === SINAIS POSITIVOS ADICIONAIS ===

        # Palavra-chave de capítulo
        if has_chapter_keyword(text):
            score += self.config.weight_chapter_keyword
            reasons.append(f"+{self.config.weight_chapter_keyword}: palavra-chave capítulo")

        # Palavra estrutural (Introdução, Conclusão, etc)
        if has_structural_keyword(text):
            score += 3
            reasons.append("+3: palavra estrutural")

        # Começa com maiúscula
        if text and text[0].isupper():
            score += self.config.weight_starts_upper
            reasons.append(f"+{self.config.weight_starts_upper}: maiúscula")

        # === SINAIS NEGATIVOS ADICIONAIS ===

        # Mesmo tamanho do corpo
        if abs(candidate.font_size - ctx.body_font_size) < self.config.font_size_tolerance:
            if not candidate.is_bold:  # Só penaliza se também não for bold
                score += self.config.penalty_same_as_body
                reasons.append(f"{self.config.penalty_same_as_body}: tamanho de corpo")

        # Sequência do mesmo tamanho (indica corpo de texto)
        if ctx.prev_font_size and ctx.next_font_size:
            if (abs(candidate.font_size - ctx.prev_font_size) < self.config.font_size_tolerance and
                abs(candidate.font_size - ctx.next_font_size) < self.config.font_size_tolerance):
                if not candidate.is_bold:
                    score += self.config.penalty_sequence
                    reasons.append(f"{self.config.penalty_sequence}: sequência")

        # Começa com minúscula (continuação de frase)
        if text and text[0].islower():
            score += self.config.penalty_lowercase_start
            reasons.append(f"{self.config.penalty_lowercase_start}: minúscula")

        return score, reasons

    def _score_accurate(
        self,
        candidate: HeadingCandidate,
        ctx: ScoringContext
    ) -> Tuple[int, List[str]]:
        """
        Estratégia ACCURATE: todas as análises disponíveis.
        Tempo alvo: < 20µs por candidato.
        """
        # Começa com score da estratégia balanced
        score, reasons = self._score_balanced(candidate, ctx)
        text = candidate.text.strip()

        # === ANÁLISE DE STOPWORDS ===
        stopword_ratio = calculate_stopword_ratio(text)
        if stopword_ratio > self.config.stopword_ratio_threshold:
            score += self.config.penalty_high_stopwords
            reasons.append(f"{self.config.penalty_high_stopwords}: {stopword_ratio:.0%} stopwords")
        elif stopword_ratio < 0.15:
            score += 1
            reasons.append("+1: poucas stopwords")

        # === ANÁLISE DE COMPRIMENTO MÉDIO ===
        # Headings tendem a ter comprimento específico (nem muito curto, nem muito longo)
        if 10 <= len(text) <= 60:
            score += 1
            reasons.append("+1: comprimento ideal")
        elif len(text) < self.config.min_heading_length:
            score -= 3
            reasons.append("-3: muito curto")

        # === ANÁLISE DE CONTEÚDO ===
        # Textos que são códigos de header (HSN002) devem ser rejeitados
        if is_repetitive_code(text):
            score -= 5
            reasons.append("-5: código repetitivo de header")

        # === ANÁLISE DE PONTUAÇÃO ===
        # Múltiplos pontos finais → provavelmente não é heading
        if text.count('.') > 1:
            score -= 1
            reasons.append("-1: múltiplos pontos")

        # Dois pontos no final → pode ser introdução de lista
        if text.endswith(':'):
            score += 1
            reasons.append("+1: termina com dois pontos")

        # === ANÁLISE DE POSIÇÃO NA PÁGINA ===
        # Headings costumam estar no topo ou após espaço
        if ctx.position_in_page < 0.15:
            score += 1
            reasons.append("+1: topo da página")

        # === DETECÇÃO DE FÓRMULAS ===
        if looks_like_formula(text):
            score -= 2
            reasons.append("-2: parece fórmula")

        # === ANÁLISE DE PALAVRAS ===
        words = text.split()
        word_count = len(words)

        # Headings geralmente têm 1-10 palavras
        if word_count > 15:
            score -= 1
            reasons.append("-1: muitas palavras")

        # === ANÁLISE DE NÚMEROS ===
        # Texto que é só números não é heading
        if text.replace(' ', '').replace('.', '').replace(',', '').isdigit():
            score -= 5
            reasons.append("-5: só números")

        # === ANÁLISE DE PALAVRAS VÁLIDAS ===
        # Precisa ter pelo menos 2 palavras com letras para ser heading confiável
        words_with_letters = [w for w in text.split() if any(c.isalpha() for c in w)]
        if len(words_with_letters) < 2 and not has_section_pattern(text):
            score -= 1
            reasons.append("-1: poucas palavras")

        return score, reasons

    def _determine_level(self, candidate: HeadingCandidate, is_heading: bool) -> int:
        """
        Determina o nível do heading (1-6) baseado no tamanho da fonte.

        Args:
            candidate: Candidato
            is_heading: Se foi determinado como heading

        Returns:
            Nível 1-6 se for heading, 0 caso contrário
        """
        if not is_heading:
            return 0

        # Busca no mapeamento
        rounded_size = round(candidate.font_size * 2) / 2

        if rounded_size in self._size_to_level:
            return self._size_to_level[rounded_size]

        # Fallback: busca o tamanho mais próximo
        if self._size_to_level:
            closest_size = min(
                self._size_to_level.keys(),
                key=lambda s: abs(s - candidate.font_size)
            )
            if abs(closest_size - candidate.font_size) < 1.0:
                return self._size_to_level[closest_size]

        # Default para H4 se não encontrar
        return 4

    def score_all(
        self,
        candidates: List[HeadingCandidate]
    ) -> List[ScoringResult]:
        """
        Aplica scoring a todos os candidatos.

        Args:
            candidates: Lista de candidatos

        Returns:
            Lista de ScoringResult
        """
        if not candidates:
            return []

        # Analisa candidatos para contexto
        self.analyze_candidates(candidates)

        results = []
        for i, candidate in enumerate(candidates):
            prev_candidate = candidates[i - 1] if i > 0 else None
            next_candidate = candidates[i + 1] if i < len(candidates) - 1 else None

            result = self.score_candidate(candidate, prev_candidate, next_candidate)
            results.append(result)

        return results

    def filter_headings(
        self,
        candidates: List[HeadingCandidate]
    ) -> List[ScoringResult]:
        """
        Filtra apenas os candidatos que são headings.

        Args:
            candidates: Lista de candidatos

        Returns:
            Lista de ScoringResult apenas para headings
        """
        all_results = self.score_all(candidates)
        return [r for r in all_results if r.is_heading]

    def benchmark(
        self,
        candidates: List[HeadingCandidate],
        iterations: int = 3
    ) -> Dict[ScoringStrategy, BenchmarkResult]:
        """
        Executa benchmark comparando todas as estratégias.

        Args:
            candidates: Lista de candidatos para teste
            iterations: Número de iterações para média

        Returns:
            Dicionário com resultados por estratégia
        """
        import sys

        results = {}
        original_strategy = self.config.strategy

        for strategy in ScoringStrategy:
            self.config.strategy = strategy

            # Reset caches
            calculate_stopword_ratio.cache_clear()
            has_section_pattern.cache_clear()
            has_chapter_keyword.cache_clear()
            is_bullet_item.cache_clear()

            times = []
            headings_count = 0
            scoring_results = []

            for _ in range(iterations):
                start = time.perf_counter()
                scoring_results = self.score_all(candidates)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
                headings_count = sum(1 for r in scoring_results if r.is_heading)

            avg_time_ms = (sum(times) / len(times)) * 1000
            avg_per_candidate_us = (avg_time_ms * 1000) / len(candidates) if candidates else 0

            # Estimativa de precisão baseada em heurísticas
            # (sem ground truth real, usamos proxy)
            if candidates:
                heading_ratio = headings_count / len(candidates)
                # Esperamos ~5-15% de headings em documento típico
                if 0.05 <= heading_ratio <= 0.15:
                    precision_estimate = 0.85
                elif 0.02 <= heading_ratio <= 0.25:
                    precision_estimate = 0.70
                else:
                    precision_estimate = 0.50
            else:
                precision_estimate = 0.0

            # Estimativa de memória (aproximada)
            memory_kb = sys.getsizeof(scoring_results) / 1024 if scoring_results else 0

            results[strategy] = BenchmarkResult(
                strategy=strategy,
                total_time_ms=avg_time_ms,
                avg_time_per_candidate_us=avg_per_candidate_us,
                candidates_processed=len(candidates),
                headings_detected=headings_count,
                precision_estimate=precision_estimate,
                memory_estimate_kb=memory_kb
            )

        # Restaura estratégia original
        self.config.strategy = original_strategy
        self._benchmark_results = list(results.values())

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do scorer."""
        return {
            "strategy": self.config.strategy.value,
            "threshold": self.config.heading_threshold,
            "body_font_size": self._body_size_cache,
            "size_to_level_mapping": self._size_to_level.copy(),
            "cache_info": {
                "stopword_ratio": calculate_stopword_ratio.cache_info()._asdict(),
                "section_pattern": has_section_pattern.cache_info()._asdict(),
            }
        }


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================

def create_candidate_from_span(
    span: Dict[str, Any],
    page_num: int,
    page_height: float
) -> HeadingCandidate:
    """
    Cria HeadingCandidate a partir de um span do PyMuPDF.

    Args:
        span: Dicionário do span (de page.get_text("dict"))
        page_num: Número da página
        page_height: Altura da página

    Returns:
        HeadingCandidate configurado
    """
    text = span.get("text", "").strip()
    font_size = span.get("size", 12.0)
    bbox = span.get("bbox", (0, 0, 0, 0))
    flags = span.get("flags", 0)
    font_name = span.get("font", "")

    is_bold, is_italic = extract_flags(flags)

    # Também detecta bold pelo nome da fonte
    if not is_bold and "bold" in font_name.lower():
        is_bold = True

    y_ratio = bbox[1] / page_height if page_height > 0 else 0.5

    return HeadingCandidate(
        text=text,
        font_size=font_size,
        page_num=page_num,
        bbox=bbox,
        y_ratio=y_ratio,
        is_bold=is_bold,
        is_italic=is_italic,
        font_name=font_name,
        flags=flags
    )


def quick_score(
    text: str,
    font_size: float,
    is_bold: bool = False,
    body_size: float = 12.0
) -> int:
    """
    Função de score rápida para uso simples.

    Args:
        text: Texto a avaliar
        font_size: Tamanho da fonte
        is_bold: Se é negrito
        body_size: Tamanho do corpo de texto

    Returns:
        Score (>= 4 indica heading)
    """
    score = 0
    text = text.strip()

    # Rejeição imediata de textos inválidos
    if not is_valid_heading_text(text, min_length=3, min_words=1):
        return -10

    # Positivos
    if has_section_pattern(text):
        score += 5
    if has_chapter_keyword(text):
        score += 4
    if has_structural_keyword(text):
        score += 3
    if is_bold:
        score += 3
    if font_size > body_size + 1.5:
        score += 2
    if text and text[0].isupper():
        score += 1

    # Negativos
    if len(text) > 120:
        score -= 5
    if text.endswith('.'):
        score -= 3
    if is_bullet_item(text):
        score -= 4
    if abs(font_size - body_size) < 0.5 and not is_bold:
        score -= 3
    if is_repetitive_code(text):
        score -= 5

    return score


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_benchmark_suite(
    candidates: List[HeadingCandidate],
    output_file: Optional[str] = None
) -> str:
    """
    Executa suite completa de benchmarks e gera relatório.

    Args:
        candidates: Lista de candidatos para teste
        output_file: Arquivo para salvar relatório (opcional)

    Returns:
        Relatório em formato string
    """
    scorer = HeadingScorer()
    results = scorer.benchmark(candidates, iterations=5)

    lines = [
        "=" * 80,
        "BENCHMARK DE ESTRATÉGIAS DE SCORING",
        "=" * 80,
        f"Total de candidatos: {len(candidates)}",
        "",
        "-" * 80,
        f"{'Estratégia':<12} {'Tempo Total':<12} {'Tempo/Item':<14} {'Headings':<10} {'Precisão Est.':<12}",
        "-" * 80,
    ]

    for strategy, result in results.items():
        lines.append(
            f"{result.strategy.value:<12} "
            f"{result.total_time_ms:>8.2f} ms  "
            f"{result.avg_time_per_candidate_us:>10.2f} µs  "
            f"{result.headings_detected:>8}  "
            f"{result.precision_estimate:>10.0%}"
        )

    lines.extend([
        "-" * 80,
        "",
        "RECOMENDAÇÃO:",
    ])

    # Determina melhor estratégia
    balanced_result = results[ScoringStrategy.BALANCED]
    fast_result = results[ScoringStrategy.FAST]
    accurate_result = results[ScoringStrategy.ACCURATE]

    # Se BALANCED é rápido o suficiente (<10ms para 1000 itens), recomenda
    if balanced_result.avg_time_per_candidate_us < 10:
        lines.append("→ BALANCED: Melhor equilíbrio entre velocidade e precisão")
    elif fast_result.avg_time_per_candidate_us < 5:
        lines.append("→ FAST: Recomendado para PDFs muito grandes")
    else:
        lines.append("→ ACCURATE: Recomendado para máxima precisão")

    lines.extend([
        "",
        "=" * 80,
    ])

    report = "\n".join(lines)

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

    return report


if __name__ == "__main__":
    # Teste básico
    print("HeadingScorer - Teste Básico")
    print("-" * 40)

    # Testa quick_score
    test_cases = [
        ("1.2 Introdução ao Tema", 14.0, True, 12.0),
        ("Este é um parágrafo normal de texto.", 12.0, False, 12.0),
        ("CAPÍTULO 3 - Metodologia", 18.0, True, 12.0),
        ("• Item de lista", 12.0, False, 12.0),
        ("Conclusão", 14.0, True, 12.0),
    ]

    print(f"{'Texto':<45} {'Score':<6} {'Heading?'}")
    print("-" * 60)

    for text, size, bold, body in test_cases:
        score = quick_score(text, size, bold, body)
        is_heading = "SIM" if score >= 3 else "NÃO"
        display_text = text[:42] + "..." if len(text) > 45 else text
        print(f"{display_text:<45} {score:>4}   {is_heading}")

    print("\n✅ Teste básico concluído!")
