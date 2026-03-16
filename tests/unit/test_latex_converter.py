"""
Testes unitários para o módulo latex_converter.

Testa a conversão de texto Unicode para LaTeX.
"""

import pytest
from app.utils.latex_converter import (
    LaTeXConverter,
    LaTeXConverterConfig,
    FormatType,
    get_latex_converter,
    to_latex,
    unicode_to_latex_char,
    needs_latex_conversion,
    GREEK_LOWER,
    GREEK_UPPER,
    MATH_OPERATORS,
    SUPERSCRIPTS,
    SUBSCRIPTS,
    MATH_FUNCTIONS,
)


class TestFormatType:
    """Testes para o enum FormatType."""

    def test_values(self):
        """Testa valores do enum."""
        assert FormatType.INLINE.value == "inline"
        assert FormatType.DISPLAY.value == "display"
        assert FormatType.RAW.value == "raw"


class TestLaTeXConverterConfig:
    """Testes para a classe LaTeXConverterConfig."""

    def test_default_values(self):
        """Testa valores padrão da configuração."""
        config = LaTeXConverterConfig()

        assert config.default_format == FormatType.INLINE
        assert config.display_threshold == 40
        assert config.convert_fractions is True
        assert config.convert_roots is True
        assert config.convert_powers is True
        assert config.convert_subscripts is True
        assert config.convert_greek is True
        assert config.convert_operators is True
        assert config.fraction_style == "frac"
        assert config.simple_fraction_inline is True
        assert config.normalize_spaces is True
        assert config.remove_duplicate_dollars is True

    def test_custom_values(self):
        """Testa valores personalizados."""
        config = LaTeXConverterConfig(
            default_format=FormatType.DISPLAY,
            display_threshold=60,
            convert_fractions=False,
            fraction_style="dfrac",
        )

        assert config.default_format == FormatType.DISPLAY
        assert config.display_threshold == 60
        assert config.convert_fractions is False
        assert config.fraction_style == "dfrac"


class TestLaTeXConverter:
    """Testes para a classe LaTeXConverter."""

    def test_init_default_config(self):
        """Testa inicialização com configuração padrão."""
        converter = LaTeXConverter()
        assert converter.config is not None
        assert converter.config.default_format == FormatType.INLINE

    def test_init_custom_config(self):
        """Testa inicialização com configuração personalizada."""
        config = LaTeXConverterConfig(display_threshold=100)
        converter = LaTeXConverter(config)
        assert converter.config.display_threshold == 100

    def test_convert_empty_string(self):
        """Testa conversão de string vazia."""
        converter = LaTeXConverter()
        result = converter.convert("")
        assert result == ""

    def test_convert_plain_text(self):
        """Testa conversão de texto sem caracteres especiais."""
        converter = LaTeXConverter()
        result = converter.convert("x + y = z", FormatType.RAW)
        # Deve preservar o texto básico
        assert "x" in result
        assert "y" in result
        assert "z" in result

    def test_convert_greek_lowercase(self):
        """Testa conversão de letras gregas minúsculas."""
        converter = LaTeXConverter()
        result = converter.convert("α + β = γ", FormatType.RAW)

        assert "\\alpha" in result
        assert "\\beta" in result
        assert "\\gamma" in result

    def test_convert_greek_uppercase(self):
        """Testa conversão de letras gregas maiúsculas."""
        converter = LaTeXConverter()
        result = converter.convert("Σ Δ Ω", FormatType.RAW)

        assert "\\Sigma" in result
        assert "\\Delta" in result
        assert "\\Omega" in result

    def test_convert_operators(self):
        """Testa conversão de operadores matemáticos."""
        converter = LaTeXConverter()
        result = converter.convert("a × b ÷ c", FormatType.RAW)

        assert "\\times" in result
        assert "\\div" in result

    def test_convert_infinity(self):
        """Testa conversão do símbolo de infinito."""
        converter = LaTeXConverter()
        result = converter.convert("∞", FormatType.RAW)

        assert "\\infty" in result

    def test_convert_sum_integral(self):
        """Testa conversão de soma e integral."""
        converter = LaTeXConverter()
        result = converter.convert("∑ ∫", FormatType.RAW)

        assert "\\sum" in result
        assert "\\int" in result

    def test_convert_superscripts(self):
        """Testa conversão de superscritos Unicode."""
        converter = LaTeXConverter()
        result = converter.convert("x²³", FormatType.RAW)

        assert "^{23}" in result

    def test_convert_subscripts(self):
        """Testa conversão de subscritos Unicode."""
        converter = LaTeXConverter()
        result = converter.convert("x₁₂", FormatType.RAW)

        assert "_{12}" in result

    def test_convert_mixed_sub_super(self):
        """Testa conversão de subscritos e superscritos mistos."""
        converter = LaTeXConverter()
        result = converter.convert("x²y₁", FormatType.RAW)

        assert "^{2}" in result
        assert "_{1}" in result

    def test_convert_fraction_simple(self):
        """Testa conversão de fração simples."""
        config = LaTeXConverterConfig(simple_fraction_inline=False)
        converter = LaTeXConverter(config)
        result = converter.convert("a/b", FormatType.RAW)

        assert "\\frac{a}{b}" in result

    def test_convert_fraction_inline_simple(self):
        """Testa que frações simples são mantidas inline."""
        config = LaTeXConverterConfig(simple_fraction_inline=True)
        converter = LaTeXConverter(config)
        result = converter.convert("a/b", FormatType.INLINE)

        # Fração simples deve ser mantida como está
        assert "a/b" in result or "\\frac" in result

    def test_convert_sqrt(self):
        """Testa conversão de raiz quadrada."""
        converter = LaTeXConverter()
        result = converter.convert("√x", FormatType.RAW)

        assert "\\sqrt{x}" in result

    def test_convert_sqrt_parentheses(self):
        """Testa conversão de raiz com parênteses."""
        converter = LaTeXConverter()
        result = converter.convert("√(x+1)", FormatType.RAW)

        assert "\\sqrt{x+1}" in result

    def test_convert_cubic_root(self):
        """Testa conversão de raiz cúbica."""
        converter = LaTeXConverter()
        result = converter.convert("∛x", FormatType.RAW)

        assert "\\sqrt[3]{x}" in result

    def test_convert_inline_format(self):
        """Testa formato inline."""
        converter = LaTeXConverter()
        result = converter.convert("x + y", FormatType.INLINE)

        assert result.startswith("$")
        assert result.endswith("$")
        assert not result.startswith("$$")

    def test_convert_display_format(self):
        """Testa formato display."""
        converter = LaTeXConverter()
        result = converter.convert("x + y", FormatType.DISPLAY)

        assert result.startswith("$$")
        assert result.endswith("$$")

    def test_convert_raw_format(self):
        """Testa formato raw (sem delimitadores)."""
        converter = LaTeXConverter()
        result = converter.convert("x + y", FormatType.RAW)

        assert not result.startswith("$")
        assert not result.endswith("$")

    def test_auto_display_for_long_formula(self):
        """Testa conversão automática para display em fórmulas longas."""
        config = LaTeXConverterConfig(display_threshold=20)
        converter = LaTeXConverter(config)
        result = converter.convert("a + b + c + d + e + f + g + h + i", FormatType.INLINE)

        # Deve ser convertido para display por ser longo
        assert result.startswith("$$")

    def test_is_already_latex_inline(self):
        """Testa detecção de LaTeX inline existente."""
        converter = LaTeXConverter()

        assert converter.is_already_latex("$x^2$") is True
        assert converter.is_already_latex("x^2") is False

    def test_is_already_latex_display(self):
        """Testa detecção de LaTeX display existente."""
        converter = LaTeXConverter()

        assert converter.is_already_latex("$$x^2$$") is True

    def test_is_already_latex_commands(self):
        """Testa detecção de comandos LaTeX existentes."""
        converter = LaTeXConverter()

        assert converter.is_already_latex("\\frac{a}{b}") is True
        assert converter.is_already_latex("\\sqrt{x}") is True
        assert converter.is_already_latex("\\alpha + \\beta") is True

    def test_convert_inline_shortcut(self):
        """Testa método convert_inline."""
        converter = LaTeXConverter()
        result = converter.convert_inline("α")

        assert result.startswith("$")
        assert "\\alpha" in result

    def test_convert_display_shortcut(self):
        """Testa método convert_display."""
        converter = LaTeXConverter()
        result = converter.convert_display("α")

        assert result.startswith("$$")
        assert "\\alpha" in result

    def test_convert_raw_shortcut(self):
        """Testa método convert_raw."""
        converter = LaTeXConverter()
        result = converter.convert_raw("α")

        assert "\\alpha" in result
        assert "$" not in result

    def test_stats_tracking(self):
        """Testa rastreamento de estatísticas."""
        converter = LaTeXConverter()
        converter.reset_stats()

        converter.convert("α²", FormatType.RAW)

        stats = converter.get_stats()
        assert stats['conversions'] >= 1
        assert stats['greek_converted'] >= 1
        assert stats['powers_converted'] >= 1

    def test_reset_stats(self):
        """Testa reset de estatísticas."""
        converter = LaTeXConverter()

        converter.convert("α²", FormatType.RAW)
        converter.reset_stats()

        stats = converter.get_stats()
        assert stats['conversions'] == 0
        assert stats['greek_converted'] == 0
        assert stats['powers_converted'] == 0


class TestFactoryFunction:
    """Testes para função factory."""

    def test_get_latex_converter_default(self):
        """Testa factory com configuração padrão."""
        converter = get_latex_converter()
        assert isinstance(converter, LaTeXConverter)

    def test_get_latex_converter_custom(self):
        """Testa factory com configuração personalizada."""
        config = LaTeXConverterConfig(display_threshold=80)
        converter = get_latex_converter(config)

        assert converter.config.display_threshold == 80


class TestToLatex:
    """Testes para função to_latex."""

    def test_inline(self):
        """Testa conversão inline."""
        result = to_latex("α + β", inline=True)

        assert result.startswith("$")
        assert "\\alpha" in result
        assert "\\beta" in result

    def test_display(self):
        """Testa conversão display."""
        result = to_latex("α + β", inline=False)

        assert result.startswith("$$")
        assert "\\alpha" in result
        assert "\\beta" in result


class TestUnicodeToLatexChar:
    """Testes para função unicode_to_latex_char."""

    def test_greek_lowercase(self):
        """Testa conversão de letra grega minúscula."""
        assert unicode_to_latex_char("α") == "\\alpha"
        assert unicode_to_latex_char("β") == "\\beta"
        assert unicode_to_latex_char("π") == "\\pi"

    def test_greek_uppercase(self):
        """Testa conversão de letra grega maiúscula."""
        assert unicode_to_latex_char("Σ") == "\\Sigma"
        assert unicode_to_latex_char("Ω") == "\\Omega"

    def test_operators(self):
        """Testa conversão de operadores."""
        assert unicode_to_latex_char("×") == "\\times"
        assert unicode_to_latex_char("÷") == "\\div"
        assert unicode_to_latex_char("∞") == "\\infty"

    def test_superscript(self):
        """Testa conversão de superscrito."""
        assert "^" in unicode_to_latex_char("²")
        assert "2" in unicode_to_latex_char("²")

    def test_subscript(self):
        """Testa conversão de subscrito."""
        assert "_" in unicode_to_latex_char("₁")
        assert "1" in unicode_to_latex_char("₁")

    def test_normal_char(self):
        """Testa que caracteres normais são preservados."""
        assert unicode_to_latex_char("x") == "x"
        assert unicode_to_latex_char("1") == "1"
        assert unicode_to_latex_char("+") == "+"


class TestNeedsLatexConversion:
    """Testes para função needs_latex_conversion."""

    def test_needs_conversion_greek(self):
        """Testa detecção de necessidade de conversão - grego."""
        assert needs_latex_conversion("α + β") is True
        assert needs_latex_conversion("Σx") is True

    def test_needs_conversion_operators(self):
        """Testa detecção de necessidade de conversão - operadores."""
        assert needs_latex_conversion("a × b") is True
        assert needs_latex_conversion("∞") is True
        assert needs_latex_conversion("∫ f(x) dx") is True

    def test_needs_conversion_scripts(self):
        """Testa detecção de necessidade de conversão - sub/superscripts."""
        assert needs_latex_conversion("x²") is True
        assert needs_latex_conversion("y₁") is True

    def test_needs_conversion_fraction(self):
        """Testa detecção de necessidade de conversão - frações."""
        assert needs_latex_conversion("a/b") is True

    def test_no_conversion_needed(self):
        """Testa texto que não precisa de conversão."""
        assert needs_latex_conversion("hello world") is False
        assert needs_latex_conversion("x + y = z") is False
        assert needs_latex_conversion("123") is False


class TestMappings:
    """Testes para os mapeamentos de caracteres."""

    def test_greek_lower_content(self):
        """Testa conteúdo de GREEK_LOWER."""
        assert 'α' in GREEK_LOWER
        assert 'β' in GREEK_LOWER
        assert 'γ' in GREEK_LOWER
        assert 'π' in GREEK_LOWER
        assert 'ω' in GREEK_LOWER

        assert GREEK_LOWER['α'] == '\\alpha'
        assert GREEK_LOWER['π'] == '\\pi'

    def test_greek_upper_content(self):
        """Testa conteúdo de GREEK_UPPER."""
        assert 'Γ' in GREEK_UPPER
        assert 'Δ' in GREEK_UPPER
        assert 'Σ' in GREEK_UPPER
        assert 'Ω' in GREEK_UPPER

        assert GREEK_UPPER['Σ'] == '\\Sigma'
        assert GREEK_UPPER['Ω'] == '\\Omega'

    def test_math_operators_content(self):
        """Testa conteúdo de MATH_OPERATORS."""
        assert '×' in MATH_OPERATORS
        assert '÷' in MATH_OPERATORS
        assert '∞' in MATH_OPERATORS
        assert '∑' in MATH_OPERATORS
        assert '∫' in MATH_OPERATORS
        assert '√' in MATH_OPERATORS

        assert MATH_OPERATORS['×'] == '\\times'
        assert MATH_OPERATORS['∞'] == '\\infty'

    def test_superscripts_content(self):
        """Testa conteúdo de SUPERSCRIPTS."""
        assert '⁰' in SUPERSCRIPTS
        assert '¹' in SUPERSCRIPTS
        assert '²' in SUPERSCRIPTS
        assert '³' in SUPERSCRIPTS
        assert 'ⁿ' in SUPERSCRIPTS

        assert SUPERSCRIPTS['²'] == '2'
        assert SUPERSCRIPTS['³'] == '3'

    def test_subscripts_content(self):
        """Testa conteúdo de SUBSCRIPTS."""
        assert '₀' in SUBSCRIPTS
        assert '₁' in SUBSCRIPTS
        assert '₂' in SUBSCRIPTS
        assert 'ₙ' in SUBSCRIPTS

        assert SUBSCRIPTS['₁'] == '1'
        assert SUBSCRIPTS['₂'] == '2'

    def test_math_functions_content(self):
        """Testa conteúdo de MATH_FUNCTIONS."""
        assert 'sin' in MATH_FUNCTIONS
        assert 'cos' in MATH_FUNCTIONS
        assert 'tan' in MATH_FUNCTIONS
        assert 'log' in MATH_FUNCTIONS
        assert 'ln' in MATH_FUNCTIONS
        assert 'exp' in MATH_FUNCTIONS
        assert 'lim' in MATH_FUNCTIONS
        assert 'sen' in MATH_FUNCTIONS  # Português


class TestRealWorldScenarios:
    """Testes com cenários do mundo real."""

    def test_physics_formula(self):
        """Testa fórmula de física."""
        converter = LaTeXConverter()
        result = converter.convert("E = mc²", FormatType.RAW)

        assert "E" in result
        assert "m" in result
        assert "c" in result
        assert "^{2}" in result

    def test_quadratic_formula(self):
        """Testa fórmula quadrática com delta."""
        converter = LaTeXConverter()
        result = converter.convert("Δ = b² - 4ac", FormatType.RAW)

        assert "\\Delta" in result
        assert "^{2}" in result

    def test_integral_notation(self):
        """Testa notação de integral."""
        converter = LaTeXConverter()
        result = converter.convert("∫ f(x) dx", FormatType.RAW)

        assert "\\int" in result
        assert "f(x)" in result

    def test_summation_notation(self):
        """Testa notação de somatório."""
        converter = LaTeXConverter()
        result = converter.convert("∑ xᵢ", FormatType.RAW)

        assert "\\sum" in result

    def test_limit_notation(self):
        """Testa notação de limite."""
        converter = LaTeXConverter()
        result = converter.convert("lim x → ∞", FormatType.RAW)

        assert "\\to" in result or "→" in result
        assert "\\infty" in result

    def test_set_notation(self):
        """Testa notação de conjuntos."""
        converter = LaTeXConverter()
        result = converter.convert("x ∈ ℝ", FormatType.RAW)

        assert "\\in" in result

    def test_inequality(self):
        """Testa desigualdades."""
        converter = LaTeXConverter()
        result = converter.convert("a ≤ b ≥ c", FormatType.RAW)

        assert "\\leq" in result
        assert "\\geq" in result

    def test_approximate(self):
        """Testa aproximação."""
        converter = LaTeXConverter()
        result = converter.convert("π ≈ 3.14", FormatType.RAW)

        assert "\\pi" in result
        assert "\\approx" in result

    def test_chemical_subscript(self):
        """Testa subscrito químico."""
        converter = LaTeXConverter()
        result = converter.convert("H₂O", FormatType.RAW)

        assert "H" in result
        assert "_{2}" in result
        assert "O" in result

    def test_trigonometric_function(self):
        """Testa função trigonométrica."""
        converter = LaTeXConverter()
        result = converter.convert("sen(θ) = cos(θ - π/2)", FormatType.RAW)

        assert "\\theta" in result
        assert "\\pi" in result
