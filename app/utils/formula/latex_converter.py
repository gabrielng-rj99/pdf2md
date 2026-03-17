r"""
Módulo de conversão robusta de Unicode para LaTeX.

Este módulo converte texto com caracteres Unicode matemáticos para
sintaxe LaTeX adequada para Markdown (GitHub/Obsidian/MarkText).

Características:
- Conversão de letras gregas Unicode → comandos LaTeX
- Conversão de operadores matemáticos Unicode → LaTeX
- Detecção e formatação de frações (a/b → \\frac{a}{b})
- Detecção e formatação de raízes (√x → \\sqrt{x})
- Detecção e formatação de potências (x² → x^{2})
- Detecção e formatação de subscritos (x₁ → x_{1})
- Formatação inline ($...$) e display ($$...$$)

Compatível com renderizadores comuns de Markdown com suporte a LaTeX.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FormatType(Enum):
    """Tipo de formatação LaTeX."""
    INLINE = "inline"     # $...$
    DISPLAY = "display"   # $$...$$
    RAW = "raw"           # Sem delimitadores


@dataclass
class LaTeXConverterConfig:
    """Configuração do conversor LaTeX."""
    # Formatação
    default_format: FormatType = FormatType.INLINE
    display_threshold: int = 40  # Caracteres para considerar display

    # Comportamento
    convert_fractions: bool = True    # a/b → \frac{a}{b}
    convert_roots: bool = True        # √x → \sqrt{x}
    convert_powers: bool = True       # x² → x^{2}
    convert_subscripts: bool = True   # x₁ → x_{1}
    convert_greek: bool = True        # α → \alpha
    convert_operators: bool = True    # × → \times

    # Frações
    fraction_style: str = "frac"      # "frac" ou "dfrac"
    simple_fraction_inline: bool = True  # Manter a/b simples se for inline

    # Limpeza
    normalize_spaces: bool = True
    remove_duplicate_dollars: bool = True


# =============================================================================
# MAPEAMENTOS UNICODE → LATEX
# =============================================================================

# Letras gregas minúsculas
GREEK_LOWER: Dict[str, str] = {
    'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
    'ε': r'\varepsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
    'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu',
    'ν': r'\nu', 'ξ': r'\xi', 'ο': 'o', 'π': r'\pi',
    'ρ': r'\rho', 'σ': r'\sigma', 'τ': r'\tau', 'υ': r'\upsilon',
    'φ': r'\varphi', 'χ': r'\chi', 'ψ': r'\psi', 'ω': r'\omega',
    'ϵ': r'\epsilon', 'ϕ': r'\phi', 'ϖ': r'\varpi', 'ϱ': r'\varrho',
    'ς': r'\varsigma', 'ϑ': r'\vartheta',
}

# Letras gregas maiúsculas
GREEK_UPPER: Dict[str, str] = {
    'Α': 'A', 'Β': 'B', 'Γ': r'\Gamma', 'Δ': r'\Delta',
    'Ε': 'E', 'Ζ': 'Z', 'Η': 'H', 'Θ': r'\Theta',
    'Ι': 'I', 'Κ': 'K', 'Λ': r'\Lambda', 'Μ': 'M',
    'Ν': 'N', 'Ξ': r'\Xi', 'Ο': 'O', 'Π': r'\Pi',
    'Ρ': 'P', 'Σ': r'\Sigma', 'Τ': 'T', 'Υ': r'\Upsilon',
    'Φ': r'\Phi', 'Χ': 'X', 'Ψ': r'\Psi', 'Ω': r'\Omega',
}

# Operadores matemáticos
MATH_OPERATORS: Dict[str, str] = {
    '×': r'\times', '÷': r'\div', '·': r'\cdot', '±': r'\pm', '∓': r'\mp',
    '≠': r'\neq', '≈': r'\approx', '≡': r'\equiv', '≅': r'\cong',
    '≤': r'\leq', '≥': r'\geq', '≪': r'\ll', '≫': r'\gg',
    '∞': r'\infty', '∝': r'\propto', '∼': r'\sim', '≃': r'\simeq',
    '∑': r'\sum', '∏': r'\prod', '∫': r'\int', '∬': r'\iint', '∭': r'\iiint',
    '∮': r'\oint', '∂': r'\partial', '∇': r'\nabla',
    '√': r'\sqrt', '∛': r'\sqrt[3]', '∜': r'\sqrt[4]',
    '∈': r'\in', '∉': r'\notin', '∋': r'\ni', '∌': r'\notni',
    '⊂': r'\subset', '⊃': r'\supset', '⊆': r'\subseteq', '⊇': r'\supseteq',
    '∩': r'\cap', '∪': r'\cup', '∅': r'\emptyset', '∖': r'\setminus',
    '∀': r'\forall', '∃': r'\exists', '∄': r'\nexists',
    '∧': r'\land', '∨': r'\lor', '¬': r'\neg', '⊕': r'\oplus', '⊗': r'\otimes',
    '→': r'\to', '←': r'\leftarrow', '↔': r'\leftrightarrow',
    '⇒': r'\Rightarrow', '⇐': r'\Leftarrow', '⇔': r'\Leftrightarrow',
    '↑': r'\uparrow', '↓': r'\downarrow', '↕': r'\updownarrow',
    '⇑': r'\Uparrow', '⇓': r'\Downarrow',
    '↦': r'\mapsto', '↪': r'\hookrightarrow',
    '°': r'^\circ', '′': "'", '″': "''", '‴': "'''",
    '∠': r'\angle', '⊥': r'\perp', '∥': r'\parallel',
    '•': r'\bullet', '⋯': r'\cdots', '⋮': r'\vdots', '⋱': r'\ddots',
    '⟨': r'\langle', '⟩': r'\rangle',
    '⌈': r'\lceil', '⌉': r'\rceil', '⌊': r'\lfloor', '⌋': r'\rfloor',
    '‖': r'\|',
}

# Superscritos Unicode → dígitos normais
SUPERSCRIPTS: Dict[str, str] = {
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
    '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    '⁺': '+', '⁻': '-', '⁼': '=', '⁽': '(', '⁾': ')',
    'ⁿ': 'n', 'ⁱ': 'i',
}

# Subscritos Unicode → dígitos normais
SUBSCRIPTS: Dict[str, str] = {
    '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
    '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
    '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')',
    'ₐ': 'a', 'ₑ': 'e', 'ₒ': 'o', 'ₓ': 'x', 'ₔ': 'schwa',
    'ₕ': 'h', 'ₖ': 'k', 'ₗ': 'l', 'ₘ': 'm', 'ₙ': 'n',
    'ₚ': 'p', 'ₛ': 's', 'ₜ': 't',
}

# Letras matemáticas itálicas Unicode (𝑎-𝑧, 𝐴-𝑍)
MATH_ITALIC_LOWER: Dict[str, str] = {
    chr(0x1D44E + i): chr(ord('a') + i) for i in range(26)
}
MATH_ITALIC_UPPER: Dict[str, str] = {
    chr(0x1D434 + i): chr(ord('A') + i) for i in range(26)
}

# Letras matemáticas bold Unicode
MATH_BOLD_LOWER: Dict[str, str] = {
    chr(0x1D41A + i): chr(ord('a') + i) for i in range(26)
}
MATH_BOLD_UPPER: Dict[str, str] = {
    chr(0x1D400 + i): chr(ord('A') + i) for i in range(26)
}

# Dígitos matemáticos
MATH_DIGITS: Dict[str, str] = {
    chr(0x1D7CE + i): str(i) for i in range(10)  # sans-serif
}

# Funções matemáticas comuns (para wrapping)
MATH_FUNCTIONS: Set[str] = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'arcsin', 'arccos', 'arctan', 'arccot',
    'sinh', 'cosh', 'tanh', 'coth',
    'sen',  # Português
    'log', 'ln', 'lg', 'exp',
    'lim', 'max', 'min', 'sup', 'inf',
    'det', 'dim', 'ker', 'Im', 'Re',
    'gcd', 'lcm', 'mod',
}


# =============================================================================
# PADRÕES REGEX
# =============================================================================

# Padrão para fração simples: a/b, (a+b)/c, etc.
FRACTION_PATTERN = re.compile(
    r'(\([^)]+\)|[a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω]+)'
    r'\s*/\s*'
    r'(\([^)]+\)|[a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω]+)'
)

# Padrão para potência: x^2, x^{2}, x², etc.
POWER_PATTERN = re.compile(
    r'([a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω\)])'
    r'\s*[\^²³⁴⁵⁶⁷⁸⁹⁰¹⁺⁻ⁿⁱ]+'
)

# Padrão para subscrito: x_1, x_{1}, x₁, etc.
SUBSCRIPT_PATTERN = re.compile(
    r'([a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω])'
    r'\s*[_₀₁₂₃₄₅₆₇₈₉ₐₑₒₓₙₕₖₗₘₚₛₜ]+'
)

# Padrão para raiz: √x, √(x+1), etc.
SQRT_PATTERN = re.compile(r'[√∛∜]\s*(\([^)]+\)|[a-zA-Z0-9]+)')

# Padrão para função: sen(x), log(x), etc.
FUNCTION_PATTERN = re.compile(
    r'\b(' + '|'.join(MATH_FUNCTIONS) + r')\s*\('
)


class LaTeXConverter:
    """
    Converte texto com Unicode matemático para LaTeX.

    Suporta conversão de:
    - Letras gregas
    - Operadores matemáticos
    - Frações
    - Potências e subscritos
    - Raízes
    - Funções matemáticas
    """

    def __init__(self, config: Optional[LaTeXConverterConfig] = None):
        """
        Inicializa o conversor.

        Args:
            config: Configuração opcional
        """
        self.config = config or LaTeXConverterConfig()
        self._build_conversion_table()
        self._stats = {
            'conversions': 0,
            'fractions_converted': 0,
            'powers_converted': 0,
            'subscripts_converted': 0,
            'greek_converted': 0,
        }

    def _build_conversion_table(self):
        """Constrói tabela de conversão completa."""
        self._char_map: Dict[str, str] = {}

        # Adicionar todos os mapeamentos
        if self.config.convert_greek:
            self._char_map.update(GREEK_LOWER)
            self._char_map.update(GREEK_UPPER)

        if self.config.convert_operators:
            self._char_map.update(MATH_OPERATORS)

        # Sempre converter letras matemáticas Unicode para ASCII
        self._char_map.update(MATH_ITALIC_LOWER)
        self._char_map.update(MATH_ITALIC_UPPER)
        self._char_map.update(MATH_BOLD_LOWER)
        self._char_map.update(MATH_BOLD_UPPER)
        self._char_map.update(MATH_DIGITS)

    def convert(
        self,
        text: str,
        format_type: Optional[FormatType] = None
    ) -> str:
        """
        Converte texto para LaTeX.

        Args:
            text: Texto a converter
            format_type: Tipo de formatação (inline/display/raw)

        Returns:
            Texto convertido para LaTeX
        """
        if not text or not text.strip():
            return text

        self._stats['conversions'] += 1

        # Determinar formato
        fmt = format_type or self.config.default_format
        if fmt == FormatType.INLINE and len(text) > self.config.display_threshold:
            fmt = FormatType.DISPLAY

        # Aplicar conversões
        result = text

        # 1. Converter raízes PRIMEIRO (antes de converter √ para \sqrt individual)
        if self.config.convert_roots:
            result = self._convert_roots(result)

        # 2. Converter superscritos Unicode (antes de chars para não quebrar)
        if self.config.convert_powers:
            result = self._convert_superscripts(result)

        # 3. Converter subscritos Unicode
        if self.config.convert_subscripts:
            result = self._convert_subscripts(result)

        # 4. Converter frações ANTES de chars (inclui conversão de gregas internamente)
        if self.config.convert_fractions:
            result = self._convert_fractions(result, fmt)

        # 5. Converter caracteres Unicode individuais (π → \pi, etc.)
        result = self._convert_chars(result)

        # 6. Formatar funções matemáticas
        result = self._format_functions(result)

        # 7. Normalizar espaços
        if self.config.normalize_spaces:
            result = re.sub(r'\s+', ' ', result)
            result = result.strip()

        # 8. Aplicar delimitadores
        if fmt == FormatType.INLINE:
            result = f'${result}$'
        elif fmt == FormatType.DISPLAY:
            result = f'$${result}$$'

        # 9. Limpar delimitadores duplicados (apenas se não for RAW)
        if self.config.remove_duplicate_dollars and fmt != FormatType.RAW:
            result = re.sub(r'\$\$\$+', '$$', result)
            # Remover $ vazio apenas se não destrói os delimitadores
            if not result.startswith('$$'):
                result = re.sub(r'\$\s*\$', '', result)

        return result

    def _convert_chars(self, text: str) -> str:
        """Converte caracteres individuais Unicode para LaTeX."""
        result = []
        greek_count = 0

        for char in text:
            if char in self._char_map:
                converted = self._char_map[char]
                result.append(converted)
                if char in GREEK_LOWER or char in GREEK_UPPER:
                    greek_count += 1
            else:
                result.append(char)

        self._stats['greek_converted'] += greek_count
        return ''.join(result)

    def _convert_superscripts(self, text: str) -> str:
        """
        Converte superscritos Unicode para notação LaTeX.

        Ex: x² → x^{2}, x²³ → x^{23}
        """
        result = []
        i = 0
        conversions = 0

        while i < len(text):
            char = text[i]

            if char in SUPERSCRIPTS:
                # Coletar todos os superscritos consecutivos
                super_chars = []
                while i < len(text) and text[i] in SUPERSCRIPTS:
                    super_chars.append(SUPERSCRIPTS[text[i]])
                    i += 1

                result.append('^{' + ''.join(super_chars) + '}')
                conversions += 1
            else:
                result.append(char)
                i += 1

        self._stats['powers_converted'] += conversions
        return ''.join(result)

    def _convert_subscripts(self, text: str) -> str:
        """
        Converte subscritos Unicode para notação LaTeX.

        Ex: x₁ → x_{1}, H₂O → H_{2}O
        """
        result = []
        i = 0
        conversions = 0

        while i < len(text):
            char = text[i]

            if char in SUBSCRIPTS:
                # Coletar todos os subscritos consecutivos
                sub_chars = []
                while i < len(text) and text[i] in SUBSCRIPTS:
                    sub_chars.append(SUBSCRIPTS[text[i]])
                    i += 1

                result.append('_{' + ''.join(sub_chars) + '}')
                conversions += 1
            else:
                result.append(char)
                i += 1

        self._stats['subscripts_converted'] += conversions
        return ''.join(result)

    def _convert_fractions(self, text: str, fmt: FormatType) -> str:
        """
        Converte frações para notação LaTeX.

        Ex: a/b → \frac{a}{b} (ou mantém a/b se inline e simples)
        """
        def convert_greek_in_text(t: str) -> str:
            """Converte letras gregas em um texto."""
            result = []
            for char in t:
                if char in self._char_map:
                    result.append(self._char_map[char])
                else:
                    result.append(char)
            return ''.join(result)

        def replace_fraction(match):
            num = match.group(1)
            den = match.group(2)

            # Se for inline e fração simples, manter como está
            if fmt == FormatType.INLINE and self.config.simple_fraction_inline:
                if len(num) <= 3 and len(den) <= 3 and '(' not in num and '(' not in den:
                    # Mesmo mantendo como fração simples, converter gregas
                    return f'{convert_greek_in_text(num)}/{convert_greek_in_text(den)}'

            # Usar \frac ou \dfrac
            frac_cmd = '\\frac' if self.config.fraction_style == 'frac' else '\\dfrac'

            # Limpar parênteses externos se presentes
            if num.startswith('(') and num.endswith(')'):
                num = num[1:-1]
            if den.startswith('(') and den.endswith(')'):
                den = den[1:-1]

            # Converter letras gregas dentro da fração
            num = convert_greek_in_text(num)
            den = convert_greek_in_text(den)

            self._stats['fractions_converted'] += 1
            return f'{frac_cmd}{{{num}}}{{{den}}}'

        return FRACTION_PATTERN.sub(replace_fraction, text)

    def _convert_roots(self, text: str) -> str:
        r"""
        Converte raízes para notação LaTeX.

        Ex: √x → \\sqrt{x}, ∛x → \\sqrt[3]{x}
        """
        # Raiz quadrada com parênteses primeiro
        text = re.sub(r'√\s*\(([^)]+)\)', '\\\\sqrt{\\1}', text)
        # Raiz quadrada sem parênteses
        text = re.sub(r'√\s*([a-zA-Z0-9])', '\\\\sqrt{\\1}', text)

        # Raiz cúbica
        text = re.sub(r'∛\s*\(([^)]+)\)', '\\\\sqrt[3]{\\1}', text)
        text = re.sub(r'∛\s*([a-zA-Z0-9])', '\\\\sqrt[3]{\\1}', text)

        # Raiz quarta
        text = re.sub(r'∜\s*\(([^)]+)\)', '\\\\sqrt[4]{\\1}', text)
        text = re.sub(r'∜\s*([a-zA-Z0-9])', '\\\\sqrt[4]{\\1}', text)

        return text

    def _format_functions(self, text: str) -> str:
        r"""
        Formata funções matemáticas com \\operatorname ou comandos específicos.

        Ex: sen(x) → \\sen(x), log(x) → \\log(x)
        """
        for func in MATH_FUNCTIONS:
            # Padrão: função seguida de ( ou espaço
            pattern = r'\b' + func + r'(?=\s*[\(\[])'

            # Funções com comandos LaTeX específicos
            if func in {'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
                        'log', 'ln', 'exp', 'lim', 'max', 'min',
                        'det', 'dim', 'ker', 'gcd', 'mod',
                        'sinh', 'cosh', 'tanh', 'coth',
                        'arcsin', 'arccos', 'arctan'}:
                replacement = '\\\\' + func
            elif func == 'sen':
                # Português - usar operatorname
                replacement = r'\\operatorname{sen}'
            else:
                replacement = r'\\operatorname{' + func + '}'

            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    def convert_inline(self, text: str) -> str:
        """Converte para formato inline ($...$)."""
        return self.convert(text, FormatType.INLINE)

    def convert_display(self, text: str) -> str:
        """Converte para formato display ($$...$$)."""
        return self.convert(text, FormatType.DISPLAY)

    def convert_raw(self, text: str) -> str:
        """Converte sem adicionar delimitadores."""
        return self.convert(text, FormatType.RAW)

    def is_already_latex(self, text: str) -> bool:
        """
        Verifica se o texto já está em formato LaTeX.

        Args:
            text: Texto a verificar

        Returns:
            True se já parece ser LaTeX
        """
        # Verificar delimitadores
        if text.startswith('$') and text.endswith('$'):
            return True
        if text.startswith('$$') and text.endswith('$$'):
            return True

        # Verificar comandos LaTeX
        latex_commands = [r'\frac', r'\sqrt', r'\sum', r'\int', r'\alpha',
                         r'\beta', r'\gamma', r'\times', r'\div']
        for cmd in latex_commands:
            if cmd in text:
                return True

        return False

    def get_stats(self) -> dict:
        """Retorna estatísticas de conversão."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'conversions': 0,
            'fractions_converted': 0,
            'powers_converted': 0,
            'subscripts_converted': 0,
            'greek_converted': 0,
        }


def get_latex_converter(config: Optional[LaTeXConverterConfig] = None) -> LaTeXConverter:
    """Factory function para obter instância do conversor."""
    return LaTeXConverter(config)


def to_latex(text: str, inline: bool = True) -> str:
    """
    Função utilitária para conversão rápida.

    Args:
        text: Texto a converter
        inline: Se True, usa formato inline; senão, display

    Returns:
        Texto convertido para LaTeX
    """
    converter = LaTeXConverter()
    fmt = FormatType.INLINE if inline else FormatType.DISPLAY
    return converter.convert(text, fmt)


def unicode_to_latex_char(char: str) -> str:
    """
    Converte um único caractere Unicode para LaTeX.

    Args:
        char: Caractere a converter

    Returns:
        Comando LaTeX ou caractere original
    """
    # Verificar em todos os mapeamentos
    if char in GREEK_LOWER:
        return GREEK_LOWER[char]
    if char in GREEK_UPPER:
        return GREEK_UPPER[char]
    if char in MATH_OPERATORS:
        return MATH_OPERATORS[char]
    if char in SUPERSCRIPTS:
        return '^{' + SUPERSCRIPTS[char] + '}'
    if char in SUBSCRIPTS:
        return '_{' + SUBSCRIPTS[char] + '}'

    return char


def needs_latex_conversion(text: str) -> bool:
    """
    Verifica se um texto precisa de conversão para LaTeX.

    Args:
        text: Texto a verificar

    Returns:
        True se contém caracteres que devem ser convertidos
    """
    all_special = (
        set(GREEK_LOWER.keys()) |
        set(GREEK_UPPER.keys()) |
        set(MATH_OPERATORS.keys()) |
        set(SUPERSCRIPTS.keys()) |
        set(SUBSCRIPTS.keys())
    )

    for char in text:
        if char in all_special:
            return True

    # Verificar padrões de fração
    if '/' in text and FRACTION_PATTERN.search(text):
        return True

    return False
