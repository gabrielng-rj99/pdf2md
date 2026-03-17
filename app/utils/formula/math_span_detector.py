"""
Módulo de detecção de spans matemáticos dentro de linhas de texto.

Este módulo identifica trechos (spans) de texto que contêm fórmulas matemáticas
dentro de linhas mistas (texto + matemática), permitindo conversão cirúrgica
para LaTeX sem afetar o texto ao redor.

Resolve o problema de conversores que envolvem linhas inteiras em $$...$$
quando apenas parte da linha é matemática.

Exemplo:
    Input:  "O valor de ρ = m/V representa a densidade"
    Output: [MathSpan(start=12, end=19, text="ρ = m/V", confidence=0.85)]

    Isso permite converter para:
    "O valor de $\\rho = \\frac{m}{V}$ representa a densidade"
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set, Dict, Iterator
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SpanType(Enum):
    """Tipo de span matemático detectado."""
    EQUATION = "equation"           # Equação com = (ex: ρ = m/V)
    FRACTION = "fraction"           # Fração (ex: a/b, 1/2)
    EXPRESSION = "expression"       # Expressão matemática geral
    VARIABLE = "variable"           # Variável isolada com subscrito/superscrito
    FUNCTION = "function"           # Função matemática (ex: f(x), sen(θ))
    GREEK_EQUATION = "greek_eq"     # Equação com símbolos gregos
    SUMMATION = "summation"         # Somatório/produto
    INTEGRAL = "integral"           # Integral
    LIMIT = "limit"                 # Limite
    ROOT = "root"                   # Raiz


@dataclass
class MathSpan:
    """Representa um span matemático detectado dentro de uma linha."""
    start: int              # Posição inicial no texto
    end: int                # Posição final no texto
    text: str               # Texto do span
    span_type: SpanType     # Tipo do span
    confidence: float       # Confiança (0.0 a 1.0)
    latex_hint: str = ""    # Sugestão de conversão LaTeX (opcional)

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class MathSpanDetectorConfig:
    """Configuração do detector de spans matemáticos."""
    # Thresholds
    min_confidence: float = 0.5
    min_span_length: int = 2
    max_span_length: int = 200

    # O que detectar
    detect_equations: bool = True
    detect_fractions: bool = True
    detect_functions: bool = True
    detect_greek: bool = True
    detect_subscripts: bool = True
    detect_superscripts: bool = True
    detect_roots: bool = True
    detect_summations: bool = True
    detect_integrals: bool = True

    # Contexto
    require_math_context: bool = True  # Exigir contexto matemático
    expand_to_boundaries: bool = True  # Expandir spans até limites naturais

    # Merge
    merge_adjacent: bool = True        # Fundir spans adjacentes
    merge_gap_threshold: int = 3       # Distância máxima para fusão


# =============================================================================
# CONJUNTOS DE CARACTERES
# =============================================================================

# Letras gregas (minúsculas e maiúsculas)
GREEK_LETTERS = set('αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ')
GREEK_LETTERS.update({'ϵ', 'ϕ', 'ϖ', 'ϱ', 'ς', 'ϑ'})  # Variantes

# Operadores matemáticos
MATH_OPERATORS = set('+-×÷·±∓=≠≈≡≤≥<>∞∝')

# Operadores de relação
RELATION_OPERATORS = set('=≠≈≡≤≥<>∼≃≅∝∈∉⊂⊃⊆⊇')

# Símbolos especiais
SPECIAL_SYMBOLS = set('∑∏∫∬∭∮∂∇√∛∜')

# Superscritos Unicode
SUPERSCRIPTS = set('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ')

# Subscritos Unicode
SUBSCRIPTS = set('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₙₕₖₗₘₚₛₜ')

# Letras matemáticas itálicas Unicode (U+1D400 range)
MATH_ITALIC_CHARS = set(chr(c) for c in range(0x1D400, 0x1D7FF + 1))

# Todos os caracteres matemáticos
ALL_MATH_CHARS = (
    GREEK_LETTERS | MATH_OPERATORS | RELATION_OPERATORS |
    SPECIAL_SYMBOLS | SUPERSCRIPTS | SUBSCRIPTS | MATH_ITALIC_CHARS
)

# Funções matemáticas
MATH_FUNCTIONS = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'arcsin', 'arccos', 'arctan', 'arccot',
    'sinh', 'cosh', 'tanh', 'coth',
    'sen', 'tg', 'cotg', 'cossec',  # Português
    'log', 'ln', 'lg', 'exp',
    'lim', 'max', 'min', 'sup', 'inf',
    'det', 'dim', 'ker', 'Im', 'Re',
    'gcd', 'lcm', 'mod', 'arg',
    'sqrt', 'root',
}

# Palavras que NÃO são matemáticas (falsos positivos comuns)
NON_MATH_WORDS = {
    'de', 'da', 'do', 'das', 'dos', 'em', 'no', 'na', 'nos', 'nas',
    'um', 'uma', 'uns', 'umas', 'o', 'a', 'os', 'as',
    'que', 'se', 'para', 'por', 'com', 'sem',
    'e', 'ou', 'mas', 'porém', 'contudo',
    'é', 'são', 'foi', 'foram', 'ser', 'estar',
    'the', 'a', 'an', 'of', 'in', 'on', 'at', 'to', 'for', 'with',
    'and', 'or', 'but', 'is', 'are', 'was', 'were',
}


# =============================================================================
# PADRÕES REGEX
# =============================================================================

# Padrão para equação simples: variável = expressão
# Usamos lista de letras gregas explicitamente para evitar problemas de range
_GREEK_LETTERS_STR = ''.join(GREEK_LETTERS)
EQUATION_PATTERN = re.compile(
    r'([a-zA-Z' + re.escape(_GREEK_LETTERS_STR) + r']\w*'  # Variável
    r'(?:[₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹]+)?)'                    # Subscrito/superscrito opcional
    r'\s*=\s*'                                              # Sinal de igual
    r'([^\s,;:.!?\)]+(?:\s*[\+\-\*/]\s*[^\s,;:.!?\)]+)*)'  # Expressão
)

# Padrão para fração: a/b
FRACTION_PATTERN = re.compile(
    r'(?<![/\w])'  # Não precedido por / ou letra
    r'(\(?[a-zA-Z0-9' + re.escape(_GREEK_LETTERS_STR) + r']+(?:[\+\-\*][a-zA-Z0-9]+)*\)?)'  # Numerador
    r'\s*/\s*'     # Divisão
    r'(\(?[a-zA-Z0-9' + re.escape(_GREEK_LETTERS_STR) + r']+(?:[\+\-\*][a-zA-Z0-9]+)*\)?)'  # Denominador
    r'(?![/\w])'   # Não seguido por / ou letra
)

# Padrão para função matemática: f(x), sen(θ), log(n)
FUNCTION_PATTERN = re.compile(
    r'\b(' + '|'.join(MATH_FUNCTIONS) + r')'  # Nome da função
    r'(?:_?\{?[a-zA-Z0-9]+\}?)?'               # Base opcional (log_2)
    r'\s*'
    r'[\(\[]'                                  # Parêntese de abertura
    r'([^)\]]+)'                               # Argumento
    r'[\)\]]',                                 # Parêntese de fechamento
    re.IGNORECASE
)

# Padrão para variável com subscrito/superscrito
VARIABLE_PATTERN = re.compile(
    r'([a-zA-Z' + re.escape(_GREEK_LETTERS_STR) + r'])'  # Letra base
    r'([₀₁₂₃₄₅₆₇₈₉ₐₑₒₓₙₕₖₗₘₚₛₜ]+|[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿⁱ]+|_\{?[a-zA-Z0-9,]+\}?|\^\{?[a-zA-Z0-9,]+\}?)'  # Sub/superscrito
)

# Padrão para letra grega isolada em contexto matemático
GREEK_CONTEXT_PATTERN = re.compile(
    r'(?:^|[\s\(=<>≤≥,;:])'  # Início ou separador
    r'([' + re.escape(_GREEK_LETTERS_STR) + r'])'  # Letra grega
    r'(?:[\s\)=<>≤≥,;:]|$)'   # Fim ou separador
)

# Padrão para equação com símbolo grego
GREEK_EQUATION_PATTERN = re.compile(
    r'([' + re.escape(_GREEK_LETTERS_STR) + r'][₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹]*)'  # Variável grega
    r'\s*=\s*'                                        # Igual
    r'([^\s,;:.!?]+(?:\s*[\+\-\*/]\s*[^\s,;:.!?]+)*)' # Expressão
)

# Padrão para expressão entre parênteses com operadores
# Nota: Escapamos os caracteres especiais do regex para evitar ranges inválidos
_MATH_OPS_ESCAPED = re.escape(''.join(MATH_OPERATORS))
PARENTHETICAL_PATTERN = re.compile(
    r'\('
    r'([^)]*[' + _MATH_OPS_ESCAPED + r'+=\-\*/\^_][^)]*)'
    r'\)'
)

# Padrão para raiz
_GREEK_ESCAPED = re.escape(''.join(GREEK_LETTERS))
ROOT_PATTERN = re.compile(
    r'[√∛∜]'
    r'[\(\{]?'
    r'([a-zA-Z0-9' + _GREEK_ESCAPED + r'\+\-\*/ ]+)'
    r'[\)\}]?'
)

# Padrão para somatório/produto
SUMMATION_PATTERN = re.compile(
    r'[∑∏]'
    r'(?:_\{?([^}]+)\}?)?'  # Limite inferior
    r'(?:\^\{?([^}]+)\}?)?'  # Limite superior
    r'\s*'
    r'([^\s]+)?'             # Expressão
)

# Padrão para integral
INTEGRAL_PATTERN = re.compile(
    r'[∫∬∭∮]'
    r'(?:_\{?([^}]+)\}?)?'  # Limite inferior
    r'(?:\^\{?([^}]+)\}?)?'  # Limite superior
    r'\s*'
    r'([^d]*)'               # Integrando
    r'd([a-zA-Z])'           # Diferencial
)

# Padrão para limite
LIMIT_PATTERN = re.compile(
    r'\blim\b'
    r'(?:_\{?([^}]+→[^}]+)\}?)?'  # Condição (x→∞)
    r'\s*'
    r'([^\s,;:.]+)?'               # Expressão
)

# Padrão para potência
POWER_PATTERN = re.compile(
    r'([a-zA-Z0-9' + re.escape(_GREEK_LETTERS_STR) + r'\)]+)'
    r'[\^²³⁴⁵⁶⁷⁸⁹⁰¹⁺⁻ⁿⁱ]+'
)

# Padrão para expressão matemática geral (sequência de variáveis e operadores)
EXPRESSION_PATTERN = re.compile(
    r'(?<![a-zA-Z])'  # Não precedido por letra
    r'([a-zA-Z' + re.escape(_GREEK_LETTERS_STR) + r'][₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹]*'  # Variável inicial
    r'(?:\s*[' + _MATH_OPS_ESCAPED + r'+=\-\*/\^_<>]\s*'  # Operador
    r'[a-zA-Z0-9' + re.escape(_GREEK_LETTERS_STR) + r'₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹\(\)]+)+)'  # Mais termos
    r'(?![a-zA-Z])'  # Não seguido por letra
)


class MathSpanDetector:
    """
    Detecta spans matemáticos dentro de linhas de texto.

    Permite identificar trechos que devem ser convertidos para LaTeX
    sem afetar o texto ao redor.
    """

    def __init__(self, config: Optional[MathSpanDetectorConfig] = None):
        """
        Inicializa o detector.

        Args:
            config: Configuração opcional
        """
        self.config = config or MathSpanDetectorConfig()
        self._stats = {
            'spans_detected': 0,
            'lines_processed': 0,
            'by_type': {t.value: 0 for t in SpanType},
        }

    def detect_spans(self, text: str) -> List[MathSpan]:
        """
        Detecta todos os spans matemáticos em uma linha de texto.

        Args:
            text: Linha de texto a analisar

        Returns:
            Lista de MathSpan ordenados por posição
        """
        if not text or len(text.strip()) < self.config.min_span_length:
            return []

        self._stats['lines_processed'] += 1
        spans: List[MathSpan] = []

        # Detectar diferentes tipos de spans
        if self.config.detect_equations:
            spans.extend(self._detect_equations(text))

        if self.config.detect_fractions:
            spans.extend(self._detect_fractions(text))

        if self.config.detect_functions:
            spans.extend(self._detect_functions(text))

        if self.config.detect_greek:
            spans.extend(self._detect_greek_equations(text))

        if self.config.detect_subscripts or self.config.detect_superscripts:
            spans.extend(self._detect_variables(text))

        if self.config.detect_roots:
            spans.extend(self._detect_roots(text))

        if self.config.detect_summations:
            spans.extend(self._detect_summations(text))

        if self.config.detect_integrals:
            spans.extend(self._detect_integrals(text))

        # Detectar expressões gerais
        spans.extend(self._detect_expressions(text))

        # Filtrar por confiança mínima
        spans = [s for s in spans if s.confidence >= self.config.min_confidence]

        # Filtrar por tamanho
        spans = [s for s in spans
                 if self.config.min_span_length <= s.length <= self.config.max_span_length]

        # Remover sobreposições
        spans = self._remove_overlaps(spans)

        # Fundir adjacentes se configurado
        if self.config.merge_adjacent:
            spans = self._merge_adjacent(spans, text)

        # Expandir até limites naturais se configurado
        if self.config.expand_to_boundaries:
            spans = [self._expand_span(s, text) for s in spans]

        # Atualizar estatísticas
        for span in spans:
            self._stats['spans_detected'] += 1
            self._stats['by_type'][span.span_type.value] += 1

        return sorted(spans, key=lambda s: s.start)

    def _detect_equations(self, text: str) -> List[MathSpan]:
        """Detecta equações (padrão: var = expressão)."""
        spans = []

        for match in EQUATION_PATTERN.finditer(text):
            var = match.group(1)
            expr = match.group(2)

            # Verificar se é realmente matemática
            if self._is_likely_math(var + '=' + expr):
                confidence = self._calculate_equation_confidence(var, expr)

                spans.append(MathSpan(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                    span_type=SpanType.EQUATION,
                    confidence=confidence,
                ))

        return spans

    def _detect_fractions(self, text: str) -> List[MathSpan]:
        """Detecta frações (padrão: a/b)."""
        spans = []

        for match in FRACTION_PATTERN.finditer(text):
            full_text = match.group(0)

            # Ignorar caminhos de arquivo e URLs
            if self._is_path_or_url(text, match.start(), match.end()):
                continue

            # Calcular confiança
            confidence = self._calculate_fraction_confidence(
                match.group(1), match.group(2)
            )

            if confidence >= 0.4:  # Threshold menor para frações
                spans.append(MathSpan(
                    start=match.start(),
                    end=match.end(),
                    text=full_text,
                    span_type=SpanType.FRACTION,
                    confidence=confidence,
                ))

        return spans

    def _detect_functions(self, text: str) -> List[MathSpan]:
        """Detecta funções matemáticas (sen(x), log(n), etc.)."""
        spans = []

        for match in FUNCTION_PATTERN.finditer(text):
            func_name = match.group(1).lower()
            argument = match.group(2)

            # Calcular confiança baseada na função e argumento
            confidence = 0.7
            if func_name in {'sin', 'cos', 'tan', 'sen', 'log', 'ln', 'exp'}:
                confidence = 0.85

            # Aumentar se argumento contém matemática
            if any(c in argument for c in GREEK_LETTERS | MATH_OPERATORS):
                confidence += 0.1

            spans.append(MathSpan(
                start=match.start(),
                end=match.end(),
                text=match.group(0),
                span_type=SpanType.FUNCTION,
                confidence=min(confidence, 1.0),
            ))

        return spans

    def _detect_greek_equations(self, text: str) -> List[MathSpan]:
        """Detecta equações com símbolos gregos."""
        spans = []

        for match in GREEK_EQUATION_PATTERN.finditer(text):
            full_text = match.group(0)

            spans.append(MathSpan(
                start=match.start(),
                end=match.end(),
                text=full_text,
                span_type=SpanType.GREEK_EQUATION,
                confidence=0.85,
            ))

        return spans

    def _detect_variables(self, text: str) -> List[MathSpan]:
        """Detecta variáveis com subscrito/superscrito."""
        spans = []

        for match in VARIABLE_PATTERN.finditer(text):
            full_text = match.group(0)

            # Ignorar se é parte de palavra comum
            start = match.start()
            end = match.end()

            # Verificar contexto
            before = text[max(0, start-1):start] if start > 0 else ''
            after = text[end:end+1] if end < len(text) else ''

            # Se está grudado com letras, provavelmente não é matemática
            if before.isalpha() or after.isalpha():
                continue

            spans.append(MathSpan(
                start=start,
                end=end,
                text=full_text,
                span_type=SpanType.VARIABLE,
                confidence=0.75,
            ))

        return spans

    def _detect_roots(self, text: str) -> List[MathSpan]:
        """Detecta raízes (√, ∛, ∜)."""
        spans = []

        for match in ROOT_PATTERN.finditer(text):
            spans.append(MathSpan(
                start=match.start(),
                end=match.end(),
                text=match.group(0),
                span_type=SpanType.ROOT,
                confidence=0.9,
            ))

        return spans

    def _detect_summations(self, text: str) -> List[MathSpan]:
        """Detecta somatórios e produtos (∑, ∏)."""
        spans = []

        for match in SUMMATION_PATTERN.finditer(text):
            spans.append(MathSpan(
                start=match.start(),
                end=match.end(),
                text=match.group(0),
                span_type=SpanType.SUMMATION,
                confidence=0.9,
            ))

        return spans

    def _detect_integrals(self, text: str) -> List[MathSpan]:
        """Detecta integrais (∫, ∬, etc.)."""
        spans = []

        for match in INTEGRAL_PATTERN.finditer(text):
            spans.append(MathSpan(
                start=match.start(),
                end=match.end(),
                text=match.group(0),
                span_type=SpanType.INTEGRAL,
                confidence=0.9,
            ))

        return spans

    def _detect_expressions(self, text: str) -> List[MathSpan]:
        """Detecta expressões matemáticas gerais."""
        spans = []

        # Expressões entre parênteses com operadores
        for match in PARENTHETICAL_PATTERN.finditer(text):
            content = match.group(1)
            if self._is_likely_math(content):
                spans.append(MathSpan(
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                    span_type=SpanType.EXPRESSION,
                    confidence=0.7,
                ))

        # Potências
        for match in POWER_PATTERN.finditer(text):
            spans.append(MathSpan(
                start=match.start(),
                end=match.end(),
                text=match.group(0),
                span_type=SpanType.EXPRESSION,
                confidence=0.8,
            ))

        # Expressões gerais com operadores
        for match in EXPRESSION_PATTERN.finditer(text):
            expr = match.group(1)
            if len(expr) >= 3 and self._is_likely_math(expr):
                # Verificar que não é falso positivo
                if not self._is_false_positive(expr, text, match.start()):
                    spans.append(MathSpan(
                        start=match.start(),
                        end=match.end(),
                        text=expr,
                        span_type=SpanType.EXPRESSION,
                        confidence=self._calculate_expression_confidence(expr),
                    ))

        return spans

    def _is_likely_math(self, text: str) -> bool:
        """Verifica se texto provavelmente contém matemática."""
        if not text:
            return False

        # Contar caracteres matemáticos
        math_chars = sum(1 for c in text if c in ALL_MATH_CHARS)
        operators = sum(1 for c in text if c in MATH_OPERATORS | {'/', '^', '_', '='})

        # Tem caracteres matemáticos?
        if math_chars > 0:
            return True

        # Tem operadores em contexto matemático?
        if operators > 0 and len(text) < 20:
            # Verificar se não é só texto
            words = text.split()
            if not all(w.lower() in NON_MATH_WORDS for w in words):
                return True

        return False

    def _is_false_positive(self, expr: str, full_text: str, start: int) -> bool:
        """Verifica se é um falso positivo comum."""
        expr_lower = expr.lower()

        # Palavras comuns que podem parecer expressões
        false_positives = {
            'e-mail', 'on-line', 'off-line', 'check-in', 'check-out',
            'know-how', 'up-to-date',
        }

        if expr_lower in false_positives:
            return True

        # Verificar contexto (se está em URL ou path)
        context_start = max(0, start - 10)
        context = full_text[context_start:start + len(expr) + 10]

        if 'http' in context.lower() or 'www.' in context.lower():
            return True

        if '://' in context or '.com' in context or '.org' in context:
            return True

        return False

    def _is_path_or_url(self, text: str, start: int, end: int) -> bool:
        """Verifica se o span está dentro de um path ou URL."""
        # Verificar contexto estendido
        context_start = max(0, start - 20)
        context_end = min(len(text), end + 20)
        context = text[context_start:context_end].lower()

        # Indicadores de path/URL
        indicators = ['http', 'https', 'ftp', 'file://', 'www.', '.png', '.jpg',
                      '.pdf', '.md', '.txt', '.html', 'images/', 'img/']

        return any(ind in context for ind in indicators)

    def _calculate_equation_confidence(self, var: str, expr: str) -> float:
        """Calcula confiança para uma equação."""
        confidence = 0.6

        # Variável é letra grega?
        if any(c in var for c in GREEK_LETTERS):
            confidence += 0.2

        # Expressão contém matemática?
        if any(c in expr for c in GREEK_LETTERS | MATH_OPERATORS):
            confidence += 0.15

        # Expressão tem fração?
        if '/' in expr:
            confidence += 0.1

        # Expressão curta (mais provável ser matemática)
        if len(expr) < 15:
            confidence += 0.05

        return min(confidence, 1.0)

    def _calculate_fraction_confidence(self, num: str, den: str) -> float:
        """Calcula confiança para uma fração."""
        confidence = 0.5

        # Ambos são simples (letra ou número)?
        if len(num) <= 3 and len(den) <= 3:
            confidence += 0.3

        # Contém letras gregas?
        if any(c in num + den for c in GREEK_LETTERS):
            confidence += 0.2

        # Números puros (1/2, 3/4)?
        if num.isdigit() and den.isdigit():
            confidence += 0.2

        # Variáveis simples (m/V, a/b)?
        if (num.isalpha() and len(num) <= 2 and
            den.isalpha() and len(den) <= 2):
            confidence += 0.25

        return min(confidence, 1.0)

    def _calculate_expression_confidence(self, expr: str) -> float:
        """Calcula confiança para uma expressão geral."""
        confidence = 0.5

        # Contar elementos matemáticos
        greek_count = sum(1 for c in expr if c in GREEK_LETTERS)
        operator_count = sum(1 for c in expr if c in MATH_OPERATORS | {'/', '^', '_', '='})

        if greek_count > 0:
            confidence += min(greek_count * 0.1, 0.3)

        if operator_count > 0:
            confidence += min(operator_count * 0.1, 0.2)

        # Comprimento adequado
        if 3 <= len(expr) <= 30:
            confidence += 0.1

        return min(confidence, 1.0)

    def _remove_overlaps(self, spans: List[MathSpan]) -> List[MathSpan]:
        """Remove spans sobrepostos, mantendo o de maior confiança."""
        if not spans:
            return []

        # Ordenar por início, depois por tamanho (maior primeiro)
        sorted_spans = sorted(spans, key=lambda s: (s.start, -s.length))

        result = []
        for span in sorted_spans:
            # Verificar sobreposição com spans já aceitos
            overlaps = False
            for existing in result:
                if self._spans_overlap(span, existing):
                    # Se o novo tem maior confiança e é maior, substituir
                    if span.confidence > existing.confidence and span.length > existing.length:
                        result.remove(existing)
                        result.append(span)
                    overlaps = True
                    break

            if not overlaps:
                result.append(span)

        return result

    def _spans_overlap(self, span1: MathSpan, span2: MathSpan) -> bool:
        """Verifica se dois spans se sobrepõem."""
        return not (span1.end <= span2.start or span2.end <= span1.start)

    def _merge_adjacent(self, spans: List[MathSpan], text: str) -> List[MathSpan]:
        """Funde spans adjacentes."""
        if len(spans) < 2:
            return spans

        sorted_spans = sorted(spans, key=lambda s: s.start)
        merged = [sorted_spans[0]]

        for span in sorted_spans[1:]:
            last = merged[-1]
            gap = span.start - last.end

            # Verificar se devem ser fundidos
            if gap <= self.config.merge_gap_threshold:
                # Verificar conteúdo entre eles
                between = text[last.end:span.start]

                # Fundir se o gap é só espaço ou operador
                if not between.strip() or between.strip() in MATH_OPERATORS | {'=', ','}:
                    # Criar span fundido
                    merged_text = text[last.start:span.end]
                    merged_span = MathSpan(
                        start=last.start,
                        end=span.end,
                        text=merged_text,
                        span_type=SpanType.EXPRESSION,
                        confidence=max(last.confidence, span.confidence),
                    )
                    merged[-1] = merged_span
                    continue

            merged.append(span)

        return merged

    def _expand_span(self, span: MathSpan, text: str) -> MathSpan:
        """Expande span até limites naturais (parênteses, espaços, etc.)."""
        start = span.start
        end = span.end

        # Expandir para incluir parênteses balanceados
        # Verificar se há parêntese de abertura antes
        if start > 0 and text[start-1] == '(':
            # Procurar fechamento
            depth = 1
            for i in range(end, len(text)):
                if text[i] == '(':
                    depth += 1
                elif text[i] == ')':
                    depth -= 1
                    if depth == 0:
                        start -= 1
                        end = i + 1
                        break

        # Não expandir além de pontuação final
        while end > start and text[end-1] in '.,;:!?':
            end -= 1

        if start != span.start or end != span.end:
            return MathSpan(
                start=start,
                end=end,
                text=text[start:end],
                span_type=span.span_type,
                confidence=span.confidence,
            )

        return span

    def detect_and_split(self, text: str) -> List[Tuple[str, bool]]:
        """
        Detecta spans e divide o texto em partes matemáticas e não-matemáticas.

        Args:
            text: Texto a processar

        Returns:
            Lista de tuplas (texto, is_math)
        """
        spans = self.detect_spans(text)

        if not spans:
            return [(text, False)]

        result = []
        last_end = 0

        for span in spans:
            # Texto antes do span (não matemático)
            if span.start > last_end:
                before = text[last_end:span.start]
                if before:
                    result.append((before, False))

            # O span (matemático)
            result.append((span.text, True))
            last_end = span.end

        # Texto depois do último span
        if last_end < len(text):
            after = text[last_end:]
            if after:
                result.append((after, False))

        return result

    def get_stats(self) -> Dict:
        """Retorna estatísticas de processamento."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'spans_detected': 0,
            'lines_processed': 0,
            'by_type': {t.value: 0 for t in SpanType},
        }


def get_math_span_detector(config: Optional[MathSpanDetectorConfig] = None) -> MathSpanDetector:
    """Factory function para obter instância do detector."""
    return MathSpanDetector(config)


def detect_math_spans(text: str) -> List[MathSpan]:
    """
    Função utilitária para detectar spans matemáticos.

    Args:
        text: Texto a analisar

    Returns:
        Lista de MathSpan detectados
    """
    detector = MathSpanDetector()
    return detector.detect_spans(text)


def split_math_and_text(text: str) -> List[Tuple[str, bool]]:
    """
    Divide texto em partes matemáticas e não-matemáticas.

    Args:
        text: Texto a dividir

    Returns:
        Lista de tuplas (texto, is_math)
    """
    detector = MathSpanDetector()
    return detector.detect_and_split(text)


def has_math_content(text: str) -> bool:
    """
    Verifica rapidamente se texto contém conteúdo matemático.

    Args:
        text: Texto a verificar

    Returns:
        True se contém matemática
    """
    if not text:
        return False

    # Verificação rápida: caracteres matemáticos óbvios
    if any(c in text for c in GREEK_LETTERS | SPECIAL_SYMBOLS | SUPERSCRIPTS | SUBSCRIPTS):
        return True

    # Verificação de padrões simples
    if re.search(r'\b\w\s*=\s*\w', text):  # Equação simples
        return True

    if re.search(r'\b\w/\w\b', text):  # Fração simples
        return True

    # Funções matemáticas
    if any(f'\\b{func}\\s*\\(' in text.lower() for func in ['sin', 'cos', 'tan', 'log', 'sen']):
        return True

    return False
