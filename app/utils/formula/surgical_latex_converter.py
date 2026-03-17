"""
Módulo de conversão cirúrgica de spans matemáticos para LaTeX.

Este módulo converte APENAS os trechos matemáticos detectados para LaTeX,
preservando o texto ao redor intacto. Resolve o problema de conversores
que envolvem linhas inteiras em $$...$$ quando apenas parte é matemática.

Pipeline:
1. MathSpanDetector identifica spans matemáticos
2. SurgicalLaTeXConverter converte apenas esses spans
3. Texto não-matemático permanece inalterado

Exemplo:
    Input:  "O valor de ρ = m/V representa a densidade"
    Output: "O valor de $\\rho = \\frac{m}{V}$ representa a densidade"
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set
from enum import Enum
import logging

from .math_span_detector import (
    MathSpanDetector, MathSpanDetectorConfig, MathSpan, SpanType,
    detect_math_spans, split_math_and_text, has_math_content,
    GREEK_LETTERS, MATH_OPERATORS, SUPERSCRIPTS, SUBSCRIPTS
)

logger = logging.getLogger(__name__)


class WrapStyle(Enum):
    """Estilo de envolvimento LaTeX."""
    INLINE = "inline"       # $...$
    DISPLAY = "display"     # $$...$$
    NONE = "none"           # Sem envolvimento


@dataclass
class SurgicalConverterConfig:
    """Configuração do conversor cirúrgico."""
    # Envolvimento
    default_wrap: WrapStyle = WrapStyle.INLINE
    display_threshold: int = 40  # Caracteres para usar display

    # Conversões
    convert_greek: bool = True
    convert_fractions: bool = True
    convert_superscripts: bool = True
    convert_subscripts: bool = True
    convert_operators: bool = True
    convert_roots: bool = True
    convert_functions: bool = True

    # Estilo de frações
    fraction_style: str = "frac"  # "frac" ou "dfrac"

    # Comportamento
    preserve_spacing: bool = True
    escape_special: bool = True

    # Detecção (passado para MathSpanDetector)
    min_confidence: float = 0.5
    merge_adjacent: bool = True


# =============================================================================
# MAPEAMENTOS UNICODE → LATEX
# =============================================================================

GREEK_TO_LATEX: Dict[str, str] = {
    # Minúsculas
    'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
    'ε': r'\varepsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
    'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu',
    'ν': r'\nu', 'ξ': r'\xi', 'ο': 'o', 'π': r'\pi',
    'ρ': r'\rho', 'σ': r'\sigma', 'τ': r'\tau', 'υ': r'\upsilon',
    'φ': r'\varphi', 'χ': r'\chi', 'ψ': r'\psi', 'ω': r'\omega',
    # Variantes
    'ϵ': r'\epsilon', 'ϕ': r'\phi', 'ϖ': r'\varpi', 'ϱ': r'\varrho',
    'ς': r'\varsigma', 'ϑ': r'\vartheta',
    # Maiúsculas
    'Α': 'A', 'Β': 'B', 'Γ': r'\Gamma', 'Δ': r'\Delta',
    'Ε': 'E', 'Ζ': 'Z', 'Η': 'H', 'Θ': r'\Theta',
    'Ι': 'I', 'Κ': 'K', 'Λ': r'\Lambda', 'Μ': 'M',
    'Ν': 'N', 'Ξ': r'\Xi', 'Ο': 'O', 'Π': r'\Pi',
    'Ρ': 'P', 'Σ': r'\Sigma', 'Τ': 'T', 'Υ': r'\Upsilon',
    'Φ': r'\Phi', 'Χ': 'X', 'Ψ': r'\Psi', 'Ω': r'\Omega',
}

OPERATOR_TO_LATEX: Dict[str, str] = {
    '×': r'\times', '÷': r'\div', '·': r'\cdot', '±': r'\pm', '∓': r'\mp',
    '≠': r'\neq', '≈': r'\approx', '≡': r'\equiv', '≅': r'\cong',
    '≤': r'\leq', '≥': r'\geq', '≪': r'\ll', '≫': r'\gg',
    '∞': r'\infty', '∝': r'\propto', '∼': r'\sim', '≃': r'\simeq',
    '∑': r'\sum', '∏': r'\prod', '∫': r'\int', '∬': r'\iint', '∭': r'\iiint',
    '∮': r'\oint', '∂': r'\partial', '∇': r'\nabla',
    '√': r'\sqrt', '∛': r'\sqrt[3]', '∜': r'\sqrt[4]',
    '∈': r'\in', '∉': r'\notin', '∋': r'\ni',
    '⊂': r'\subset', '⊃': r'\supset', '⊆': r'\subseteq', '⊇': r'\supseteq',
    '∩': r'\cap', '∪': r'\cup', '∅': r'\emptyset', '∖': r'\setminus',
    '∀': r'\forall', '∃': r'\exists', '∄': r'\nexists',
    '∧': r'\land', '∨': r'\lor', '¬': r'\neg',
    '→': r'\to', '←': r'\leftarrow', '↔': r'\leftrightarrow',
    '⇒': r'\Rightarrow', '⇐': r'\Leftarrow', '⇔': r'\Leftrightarrow',
    '↑': r'\uparrow', '↓': r'\downarrow',
    '°': r'^\circ', '′': "'", '″': "''",
    '∠': r'\angle', '⊥': r'\perp', '∥': r'\parallel',
    '⟨': r'\langle', '⟩': r'\rangle',
}

SUPERSCRIPT_TO_DIGIT: Dict[str, str] = {
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    '⁺': '+', '⁻': '-', '⁼': '=', '⁽': '(', '⁾': ')',
    'ⁿ': 'n', 'ⁱ': 'i',
}

SUBSCRIPT_TO_DIGIT: Dict[str, str] = {
    '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
    '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
    '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')',
    'ₐ': 'a', 'ₑ': 'e', 'ₒ': 'o', 'ₓ': 'x', 'ₔ': 'schwa',
    'ₕ': 'h', 'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm', 'ₙ': 'n',
    'ₚ': 'p', 'ₛ': 's', 'ₜ': 't',
}

# Funções matemáticas que precisam de \
LATEX_FUNCTIONS: Set[str] = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'arcsin', 'arccos', 'arctan', 'arccot',
    'sinh', 'cosh', 'tanh', 'coth',
    'log', 'ln', 'lg', 'exp',
    'lim', 'max', 'min', 'sup', 'inf',
    'det', 'dim', 'ker', 'arg',
    'gcd', 'mod',
}

# Funções em português que mapeiam para LaTeX
PORTUGUESE_FUNCTIONS: Dict[str, str] = {
    'sen': r'\sin',
    'tg': r'\tan',
    'cotg': r'\cot',
    'cossec': r'\csc',
    'arcsen': r'\arcsin',
    'arctg': r'\arctan',
}


# =============================================================================
# PADRÕES REGEX PARA CONVERSÃO
# =============================================================================

# Fração simples: a/b
FRACTION_PATTERN = re.compile(
    r'(\(?[a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ]+'
    r'(?:[\+\-\*][a-zA-Z0-9]+)*\)?)'
    r'\s*/\s*'
    r'(\(?[a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ]+'
    r'(?:[\+\-\*][a-zA-Z0-9]+)*\)?)'
)

# Superscrito Unicode: x² → x^{2}
UNICODE_SUPERSCRIPT_PATTERN = re.compile(
    r'([a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ\)])'
    r'([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ]+)'
)

# Subscrito Unicode: x₁ → x_{1}
UNICODE_SUBSCRIPT_PATTERN = re.compile(
    r'([a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ])'
    r'([₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₙₕₖₗₘₚₛₜ]+)'
)

# Raiz: √x ou √(x+1)
ROOT_PATTERN = re.compile(
    r'([√∛∜])\s*'
    r'(?:\(([^)]+)\)|([a-zA-Z0-9]+))'
)

# Função matemática: sin(x), log_2(x)
FUNCTION_PATTERN = re.compile(
    r'\b(' + '|'.join(LATEX_FUNCTIONS | set(PORTUGUESE_FUNCTIONS.keys())) + r')\b'
    r'(?:_([a-zA-Z0-9]+))?'
    r'\s*\(([^)]+)\)',
    re.IGNORECASE
)


class SurgicalLaTeXConverter:
    """
    Converte spans matemáticos para LaTeX de forma cirúrgica.

    Preserva texto não-matemático e converte apenas os trechos identificados
    como matemáticos pelo MathSpanDetector.
    """

    def __init__(self, config: Optional[SurgicalConverterConfig] = None):
        """
        Inicializa o conversor.

        Args:
            config: Configuração opcional
        """
        self.config = config or SurgicalConverterConfig()

        # Configurar detector de spans
        detector_config = MathSpanDetectorConfig(
            min_confidence=self.config.min_confidence,
            merge_adjacent=self.config.merge_adjacent,
        )
        self.span_detector = MathSpanDetector(detector_config)

        self._stats = {
            'lines_processed': 0,
            'spans_converted': 0,
            'greek_converted': 0,
            'fractions_converted': 0,
            'superscripts_converted': 0,
            'subscripts_converted': 0,
        }

    def convert_text(self, text: str) -> str:
        """
        Converte texto completo (múltiplas linhas).

        Args:
            text: Texto a converter

        Returns:
            Texto com spans matemáticos convertidos para LaTeX
        """
        if not text:
            return text

        lines = text.split('\n')
        converted_lines = [self.convert_line(line) for line in lines]
        return '\n'.join(converted_lines)

    def convert_line(self, line: str) -> str:
        """
        Converte uma única linha.

        Args:
            line: Linha a converter

        Returns:
            Linha com spans matemáticos convertidos
        """
        if not line or not line.strip():
            return line

        self._stats['lines_processed'] += 1

        # Verificação rápida: tem conteúdo matemático?
        if not has_math_content(line):
            return line

        # Detectar spans matemáticos
        spans = self.span_detector.detect_spans(line)

        if not spans:
            return line

        # Converter spans de trás para frente (para não invalidar posições)
        result = line
        for span in sorted(spans, key=lambda s: s.start, reverse=True):
            converted = self._convert_span(span)
            result = result[:span.start] + converted + result[span.end:]
            self._stats['spans_converted'] += 1

        return result

    def _convert_span(self, span: MathSpan) -> str:
        """
        Converte um span matemático para LaTeX.

        Args:
            span: Span a converter

        Returns:
            Texto LaTeX
        """
        text = span.text

        # Aplicar conversões
        if self.config.convert_greek:
            text = self._convert_greek(text)

        if self.config.convert_fractions:
            text = self._convert_fractions(text)

        if self.config.convert_superscripts:
            text = self._convert_superscripts(text)

        if self.config.convert_subscripts:
            text = self._convert_subscripts(text)

        if self.config.convert_operators:
            text = self._convert_operators(text)

        if self.config.convert_roots:
            text = self._convert_roots(text)

        if self.config.convert_functions:
            text = self._convert_functions(text)

        # Determinar estilo de envolvimento
        wrap_style = self._determine_wrap_style(span, text)

        # Envolver em delimitadores LaTeX
        return self._wrap_latex(text, wrap_style)

    def _convert_greek(self, text: str) -> str:
        """Converte letras gregas Unicode para comandos LaTeX."""
        for greek, latex in GREEK_TO_LATEX.items():
            if greek in text:
                # Adicionar espaço após comando se seguido por letra
                # Usamos função de substituição para evitar problemas com backslashes
                def add_space(match):
                    return latex + ' ' + match.group(1)

                text = re.sub(
                    re.escape(greek) + r'([a-zA-Z])',
                    add_space,
                    text
                )
                # Conversão simples para outros casos
                text = text.replace(greek, latex)
                self._stats['greek_converted'] += 1

        return text

    def _convert_fractions(self, text: str) -> str:
        """Converte frações para \\frac{}{} LaTeX."""
        def replace_fraction(match):
            num = match.group(1)
            den = match.group(2)

            # Remover parênteses se presentes
            num = num.strip('()')
            den = den.strip('()')

            # Converter componentes recursivamente
            num = self._convert_greek(num)
            den = self._convert_greek(den)

            self._stats['fractions_converted'] += 1

            style = self.config.fraction_style
            return rf'\{style}{{{num}}}{{{den}}}'

        return FRACTION_PATTERN.sub(replace_fraction, text)

    def _convert_superscripts(self, text: str) -> str:
        """Converte superscritos Unicode para ^{} LaTeX."""
        def replace_superscript(match):
            base = match.group(1)
            sup = match.group(2)

            # Converter cada caractere superscrito
            converted = ''.join(SUPERSCRIPT_TO_DIGIT.get(c, c) for c in sup)

            self._stats['superscripts_converted'] += 1

            if len(converted) == 1:
                return f'{base}^{converted}'
            else:
                return f'{base}^{{{converted}}}'

        return UNICODE_SUPERSCRIPT_PATTERN.sub(replace_superscript, text)

    def _convert_subscripts(self, text: str) -> str:
        """Converte subscritos Unicode para _{} LaTeX."""
        def replace_subscript(match):
            base = match.group(1)
            sub = match.group(2)

            # Converter cada caractere subscrito
            converted = ''.join(SUBSCRIPT_TO_DIGIT.get(c, c) for c in sub)

            self._stats['subscripts_converted'] += 1

            if len(converted) == 1:
                return f'{base}_{converted}'
            else:
                return f'{base}_{{{converted}}}'

        return UNICODE_SUBSCRIPT_PATTERN.sub(replace_subscript, text)

    def _convert_operators(self, text: str) -> str:
        """Converte operadores Unicode para LaTeX."""
        for op, latex in OPERATOR_TO_LATEX.items():
            if op in text:
                text = text.replace(op, f' {latex} ')

        # Limpar espaços extras
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _convert_roots(self, text: str) -> str:
        """Converte raízes para \\sqrt LaTeX."""
        def replace_root(match):
            root_char = match.group(1)
            arg_paren = match.group(2)  # Argumento entre parênteses
            arg_simple = match.group(3)  # Argumento simples

            arg = arg_paren or arg_simple
            arg = self._convert_greek(arg)

            if root_char == '√':
                return rf'\sqrt{{{arg}}}'
            elif root_char == '∛':
                return rf'\sqrt[3]{{{arg}}}'
            elif root_char == '∜':
                return rf'\sqrt[4]{{{arg}}}'

            return match.group(0)

        return ROOT_PATTERN.sub(replace_root, text)

    def _convert_functions(self, text: str) -> str:
        """Converte funções matemáticas para LaTeX."""
        def replace_function(match):
            func_name = match.group(1).lower()
            base = match.group(2)  # Base opcional (log_2)
            arg = match.group(3)

            # Mapear função para LaTeX
            if func_name in PORTUGUESE_FUNCTIONS:
                latex_func = PORTUGUESE_FUNCTIONS[func_name]
            elif func_name in LATEX_FUNCTIONS:
                latex_func = f'\\{func_name}'
            else:
                latex_func = func_name

            # Converter argumento
            arg = self._convert_greek(arg)

            if base:
                return f'{latex_func}_{{{base}}}({arg})'
            else:
                return f'{latex_func}({arg})'

        return FUNCTION_PATTERN.sub(replace_function, text)

    def _determine_wrap_style(self, span: MathSpan, converted_text: str) -> WrapStyle:
        """Determina o estilo de envolvimento LaTeX."""
        # Usar configuração padrão
        if self.config.default_wrap == WrapStyle.NONE:
            return WrapStyle.NONE

        # Display para expressões longas ou tipos específicos
        if len(converted_text) > self.config.display_threshold:
            return WrapStyle.DISPLAY

        if span.span_type in {SpanType.SUMMATION, SpanType.INTEGRAL}:
            return WrapStyle.DISPLAY

        return WrapStyle.INLINE

    def _wrap_latex(self, text: str, style: WrapStyle) -> str:
        """Envolve texto em delimitadores LaTeX."""
        if style == WrapStyle.NONE:
            return text
        elif style == WrapStyle.DISPLAY:
            return f'$${text}$$'
        else:  # INLINE
            return f'${text}$'

    def convert_span_only(self, text: str) -> str:
        """
        Converte apenas o conteúdo matemático sem envolver em $.

        Útil quando você já sabe que o texto é matemático.

        Args:
            text: Texto matemático

        Returns:
            Texto LaTeX sem delimitadores
        """
        if self.config.convert_greek:
            text = self._convert_greek(text)

        if self.config.convert_fractions:
            text = self._convert_fractions(text)

        if self.config.convert_superscripts:
            text = self._convert_superscripts(text)

        if self.config.convert_subscripts:
            text = self._convert_subscripts(text)

        if self.config.convert_operators:
            text = self._convert_operators(text)

        if self.config.convert_roots:
            text = self._convert_roots(text)

        if self.config.convert_functions:
            text = self._convert_functions(text)

        return text

    def get_stats(self) -> Dict:
        """Retorna estatísticas de processamento."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'lines_processed': 0,
            'spans_converted': 0,
            'greek_converted': 0,
            'fractions_converted': 0,
            'superscripts_converted': 0,
            'subscripts_converted': 0,
        }


def get_surgical_converter(config: Optional[SurgicalConverterConfig] = None) -> SurgicalLaTeXConverter:
    """Factory function para obter instância do conversor."""
    return SurgicalLaTeXConverter(config)


def convert_math_to_latex(text: str, wrap: bool = True) -> str:
    """
    Função utilitária para converter matemática para LaTeX.

    Args:
        text: Texto a converter
        wrap: Se deve envolver em $...$

    Returns:
        Texto com matemática convertida para LaTeX
    """
    config = SurgicalConverterConfig(
        default_wrap=WrapStyle.INLINE if wrap else WrapStyle.NONE
    )
    converter = SurgicalLaTeXConverter(config)
    return converter.convert_text(text)


def convert_line_to_latex(line: str) -> str:
    """
    Converte uma linha, preservando texto não-matemático.

    Args:
        line: Linha a converter

    Returns:
        Linha com spans matemáticos convertidos
    """
    converter = SurgicalLaTeXConverter()
    return converter.convert_line(line)


def greek_to_latex(text: str) -> str:
    """
    Converte apenas letras gregas para LaTeX.

    Args:
        text: Texto com letras gregas Unicode

    Returns:
        Texto com comandos LaTeX
    """
    for greek, latex in GREEK_TO_LATEX.items():
        if greek in text:
            text = text.replace(greek, latex)
    return text


def fraction_to_latex(num: str, den: str, style: str = "frac") -> str:
    """
    Cria uma fração LaTeX.

    Args:
        num: Numerador
        den: Denominador
        style: "frac" ou "dfrac"

    Returns:
        String LaTeX da fração
    """
    return rf'\{style}{{{num}}}{{{den}}}'


def needs_conversion(text: str) -> bool:
    """
    Verifica se texto precisa de conversão LaTeX.

    Args:
        text: Texto a verificar

    Returns:
        True se contém elementos que precisam conversão
    """
    if not text:
        return False

    # Letras gregas
    if any(c in text for c in GREEK_LETTERS):
        return True

    # Operadores especiais
    if any(c in text for c in OPERATOR_TO_LATEX.keys()):
        return True

    # Superscritos/subscritos Unicode
    if any(c in text for c in SUPERSCRIPTS | SUBSCRIPTS):
        return True

    # Raízes
    if any(c in text for c in '√∛∜'):
        return True

    return False
