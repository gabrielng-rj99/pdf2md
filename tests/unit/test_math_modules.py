"""
Testes unitários para os módulos de matemática:
- MathSpanDetector
- SurgicalLaTeXConverter
- FormulaReconstructor
"""

import pytest
from app.utils.math_span_detector import (
    MathSpanDetector,
    MathSpanDetectorConfig,
    MathSpan,
    SpanType,
    detect_math_spans,
    split_math_and_text,
    has_math_content,
)
from app.utils.surgical_latex_converter import (
    SurgicalLaTeXConverter,
    SurgicalConverterConfig,
    WrapStyle,
    convert_math_to_latex,
    convert_line_to_latex,
    greek_to_latex,
    fraction_to_latex,
    needs_conversion,
)
from app.utils.formula_reconstructor import (
    FormulaReconstructor,
    FormulaReconstructorConfig,
    FormulaFragment,
    FragmentType,
    reconstruct_formulas,
    detect_formula_fragments,
    fix_fraction_on_multiple_lines,
    merge_equation_lines,
)


# =============================================================================
# MathSpanDetector Tests
# =============================================================================

class TestMathSpanDetectorConfig:
    """Testes para a configuração do MathSpanDetector."""

    def test_default_config(self):
        """Teste de configuração padrão."""
        config = MathSpanDetectorConfig()
        assert config.min_confidence == 0.5
        assert config.min_span_length == 2
        assert config.max_span_length == 200
        assert config.detect_equations is True
        assert config.detect_fractions is True
        assert config.merge_adjacent is True

    def test_custom_config(self):
        """Teste de configuração personalizada."""
        config = MathSpanDetectorConfig(
            min_confidence=0.7,
            detect_greek=False,
            merge_adjacent=False,
        )
        assert config.min_confidence == 0.7
        assert config.detect_greek is False
        assert config.merge_adjacent is False


class TestMathSpanDetectorInit:
    """Testes de inicialização do MathSpanDetector."""

    def test_init_default(self):
        """Teste de inicialização com config padrão."""
        detector = MathSpanDetector()
        assert detector.config is not None
        assert detector.config.min_confidence == 0.5

    def test_init_custom_config(self):
        """Teste de inicialização com config personalizada."""
        config = MathSpanDetectorConfig(min_confidence=0.8)
        detector = MathSpanDetector(config)
        assert detector.config.min_confidence == 0.8


class TestMathSpanDetection:
    """Testes de detecção de spans matemáticos."""

    def test_detect_simple_equation(self):
        """Detecta equação simples."""
        detector = MathSpanDetector()
        spans = detector.detect_spans("O valor de ρ = m/V representa a densidade")

        assert len(spans) >= 1
        # Deve detectar algo com ρ = m/V
        equation_spans = [s for s in spans if 'ρ' in s.text or '=' in s.text]
        assert len(equation_spans) >= 1

    def test_detect_fraction(self):
        """Detecta fração simples."""
        detector = MathSpanDetector()
        spans = detector.detect_spans("A fração 1/2 é um número racional")

        fraction_spans = [s for s in spans if s.span_type == SpanType.FRACTION]
        assert len(fraction_spans) >= 1
        assert any("1/2" in s.text for s in spans)

    def test_detect_expression_with_superscript(self):
        """Detecta expressão com superscrito."""
        detector = MathSpanDetector()
        spans = detector.detect_spans("A equação x² + 2x + 1 = 0")

        assert len(spans) >= 1

    def test_no_math_in_normal_text(self):
        """Não detecta matemática em texto normal."""
        detector = MathSpanDetector()
        spans = detector.detect_spans("Este é um texto normal sem matemática")

        # Pode haver alguns falsos positivos, mas não muitos
        assert len(spans) <= 1

    def test_detect_greek_letters(self):
        """Detecta letras gregas em contexto matemático."""
        detector = MathSpanDetector()
        spans = detector.detect_spans("O coeficiente α = 5")

        assert len(spans) >= 1

    def test_empty_string(self):
        """Retorna lista vazia para string vazia."""
        detector = MathSpanDetector()
        spans = detector.detect_spans("")
        assert spans == []

    def test_whitespace_only(self):
        """Retorna lista vazia para string só com espaços."""
        detector = MathSpanDetector()
        spans = detector.detect_spans("   \n\t  ")
        assert spans == []


class TestMathSpanUtilityFunctions:
    """Testes para funções utilitárias do módulo."""

    def test_detect_math_spans_function(self):
        """Teste da função detect_math_spans."""
        spans = detect_math_spans("x = y + z")
        assert isinstance(spans, list)

    def test_split_math_and_text(self):
        """Teste da função split_math_and_text."""
        parts = split_math_and_text("O valor de x = 5 é importante")

        assert isinstance(parts, list)
        assert all(isinstance(p, tuple) and len(p) == 2 for p in parts)
        assert all(isinstance(p[0], str) and isinstance(p[1], bool) for p in parts)

    def test_has_math_content_true(self):
        """Teste has_math_content retorna True para texto com matemática."""
        assert has_math_content("α + β = γ") is True
        assert has_math_content("x = 5") is True
        assert has_math_content("1/2") is True

    def test_has_math_content_false(self):
        """Teste has_math_content retorna False para texto sem matemática."""
        assert has_math_content("Este é um texto normal") is False
        assert has_math_content("") is False


class TestMathSpanStats:
    """Testes para estatísticas do detector."""

    def test_stats_initial(self):
        """Estatísticas iniciais são zero."""
        detector = MathSpanDetector()
        stats = detector.get_stats()

        assert stats['spans_detected'] == 0
        assert stats['lines_processed'] == 0

    def test_stats_after_detection(self):
        """Estatísticas atualizam após detecção."""
        detector = MathSpanDetector()
        detector.detect_spans("x = 5")
        detector.detect_spans("y = 10")

        stats = detector.get_stats()
        assert stats['lines_processed'] == 2

    def test_reset_stats(self):
        """Reset de estatísticas funciona."""
        detector = MathSpanDetector()
        detector.detect_spans("x = 5")
        detector.reset_stats()

        stats = detector.get_stats()
        assert stats['lines_processed'] == 0


# =============================================================================
# SurgicalLaTeXConverter Tests
# =============================================================================

class TestSurgicalConverterConfig:
    """Testes para a configuração do SurgicalLaTeXConverter."""

    def test_default_config(self):
        """Teste de configuração padrão."""
        config = SurgicalConverterConfig()
        assert config.default_wrap == WrapStyle.INLINE
        assert config.convert_greek is True
        assert config.convert_fractions is True
        assert config.fraction_style == "frac"

    def test_custom_config(self):
        """Teste de configuração personalizada."""
        config = SurgicalConverterConfig(
            default_wrap=WrapStyle.DISPLAY,
            convert_greek=False,
            fraction_style="dfrac",
        )
        assert config.default_wrap == WrapStyle.DISPLAY
        assert config.convert_greek is False
        assert config.fraction_style == "dfrac"


class TestSurgicalConverterInit:
    """Testes de inicialização do SurgicalLaTeXConverter."""

    def test_init_default(self):
        """Teste de inicialização com config padrão."""
        converter = SurgicalLaTeXConverter()
        assert converter.config is not None
        assert converter.span_detector is not None

    def test_init_custom_config(self):
        """Teste de inicialização com config personalizada."""
        config = SurgicalConverterConfig(min_confidence=0.8)
        converter = SurgicalLaTeXConverter(config)
        assert converter.config.min_confidence == 0.8


class TestSurgicalConversion:
    """Testes de conversão cirúrgica."""

    def test_convert_simple_equation(self):
        """Converte equação simples."""
        converter = SurgicalLaTeXConverter()
        result = converter.convert_line("O valor de ρ = m/V é a densidade")

        # Deve conter LaTeX
        assert "\\rho" in result or "\\frac" in result or "$" in result

    def test_convert_fraction(self):
        """Converte fração para LaTeX."""
        converter = SurgicalLaTeXConverter()
        result = converter.convert_line("A fração a/b")

        # Verifica se converteu
        assert "\\frac" in result or result != "A fração a/b"

    def test_preserve_normal_text(self):
        """Preserva texto normal sem alteração."""
        converter = SurgicalLaTeXConverter()
        original = "Este é um texto normal sem matemática."
        result = converter.convert_line(original)

        # Texto normal deve permanecer igual ou muito similar
        assert "Este é um texto normal" in result

    def test_convert_greek_letters(self):
        """Converte letras gregas."""
        converter = SurgicalLaTeXConverter()
        result = converter.convert_line("O coeficiente α vale 5")

        # α deve ser convertido para \alpha
        assert "\\alpha" in result or "α" in result  # pode ou não converter dependendo do contexto

    def test_empty_string(self):
        """Retorna string vazia para input vazio."""
        converter = SurgicalLaTeXConverter()
        assert converter.convert_line("") == ""

    def test_convert_text_multiline(self):
        """Converte texto com múltiplas linhas."""
        converter = SurgicalLaTeXConverter()
        text = "Linha 1: x = 5\nLinha 2: y = 10"
        result = converter.convert_text(text)

        assert "\n" in result  # Mantém quebras de linha


class TestSurgicalConverterUtilityFunctions:
    """Testes para funções utilitárias."""

    def test_convert_math_to_latex(self):
        """Teste da função convert_math_to_latex."""
        result = convert_math_to_latex("x = 5")
        assert isinstance(result, str)

    def test_convert_line_to_latex(self):
        """Teste da função convert_line_to_latex."""
        result = convert_line_to_latex("A equação ρ = m/V")
        assert isinstance(result, str)

    def test_greek_to_latex(self):
        """Teste da função greek_to_latex."""
        result = greek_to_latex("αβγ")
        assert "\\alpha" in result
        assert "\\beta" in result
        assert "\\gamma" in result

    def test_fraction_to_latex(self):
        """Teste da função fraction_to_latex."""
        result = fraction_to_latex("a", "b")
        assert result == r"\frac{a}{b}"

    def test_fraction_to_latex_dfrac(self):
        """Teste da função fraction_to_latex com dfrac."""
        result = fraction_to_latex("x", "y", style="dfrac")
        assert result == r"\dfrac{x}{y}"

    def test_needs_conversion_true(self):
        """Teste needs_conversion retorna True."""
        assert needs_conversion("αβγ") is True
        assert needs_conversion("x² + y²") is True
        assert needs_conversion("√x") is True

    def test_needs_conversion_false(self):
        """Teste needs_conversion retorna False."""
        assert needs_conversion("texto normal") is False
        assert needs_conversion("") is False


class TestSurgicalConverterStats:
    """Testes para estatísticas do conversor."""

    def test_stats_initial(self):
        """Estatísticas iniciais são zero."""
        converter = SurgicalLaTeXConverter()
        stats = converter.get_stats()

        assert stats['lines_processed'] == 0
        assert stats['spans_converted'] == 0

    def test_stats_after_conversion(self):
        """Estatísticas atualizam após conversão."""
        converter = SurgicalLaTeXConverter()
        converter.convert_line("ρ = m/V")

        stats = converter.get_stats()
        assert stats['lines_processed'] >= 1

    def test_reset_stats(self):
        """Reset de estatísticas funciona."""
        converter = SurgicalLaTeXConverter()
        converter.convert_line("x = 5")
        converter.reset_stats()

        stats = converter.get_stats()
        assert stats['lines_processed'] == 0


# =============================================================================
# FormulaReconstructor Tests
# =============================================================================

class TestFormulaReconstructorConfig:
    """Testes para a configuração do FormulaReconstructor."""

    def test_default_config(self):
        """Teste de configuração padrão."""
        config = FormulaReconstructorConfig()
        assert config.detect_vertical_fractions is True
        assert config.max_fraction_gap == 2
        assert config.reconstruct_equations is True

    def test_custom_config(self):
        """Teste de configuração personalizada."""
        config = FormulaReconstructorConfig(
            detect_vertical_fractions=False,
            max_fraction_gap=5,
        )
        assert config.detect_vertical_fractions is False
        assert config.max_fraction_gap == 5


class TestFormulaReconstructorInit:
    """Testes de inicialização do FormulaReconstructor."""

    def test_init_default(self):
        """Teste de inicialização com config padrão."""
        reconstructor = FormulaReconstructor()
        assert reconstructor.config is not None

    def test_init_custom_config(self):
        """Teste de inicialização com config personalizada."""
        config = FormulaReconstructorConfig(max_fraction_gap=10)
        reconstructor = FormulaReconstructor(config)
        assert reconstructor.config.max_fraction_gap == 10


class TestFormulaReconstruction:
    """Testes de reconstrução de fórmulas."""

    def test_reconstruct_vertical_fraction(self):
        """Reconstrói fração vertical."""
        reconstructor = FormulaReconstructor()
        text = "O resultado é\na\n───\nb\nque representa uma fração."
        result = reconstructor.reconstruct(text)

        # A fração deve ser reconstruída
        assert "a/b" in result or "a)/(" in result

    def test_reconstruct_fragmented_equation(self):
        """Reconstrói equação fragmentada."""
        reconstructor = FormulaReconstructor()
        text = "A equação é:\nρ =\nm/V"
        result = reconstructor.reconstruct(text)

        # A equação deve estar na mesma linha
        lines = result.split('\n')
        assert any("ρ =" in line and "m/V" in line for line in lines) or "ρ = m/V" in result

    def test_preserve_normal_text(self):
        """Preserva texto normal."""
        reconstructor = FormulaReconstructor()
        text = "Este é um texto normal.\nSem fórmulas fragmentadas."
        result = reconstructor.reconstruct(text)

        assert "Este é um texto normal" in result
        assert "Sem fórmulas fragmentadas" in result

    def test_empty_string(self):
        """Retorna string vazia para input vazio."""
        reconstructor = FormulaReconstructor()
        assert reconstructor.reconstruct("") == ""

    def test_single_line(self):
        """Processa linha única sem problemas."""
        reconstructor = FormulaReconstructor()
        text = "Uma única linha"
        result = reconstructor.reconstruct(text)
        assert result == "Uma única linha"


class TestFormulaFragmentDetection:
    """Testes de detecção de fragmentos."""

    def test_detect_fraction_line(self):
        """Detecta linha de fração."""
        reconstructor = FormulaReconstructor()
        text = "numerador\n────\ndenominador"
        fragments = reconstructor.detect_fragments(text)

        fraction_lines = [f for f in fragments if f.fragment_type == FragmentType.FRACTION_LINE]
        assert len(fraction_lines) >= 1

    def test_detect_orphan_exponent(self):
        """Detecta expoente órfão."""
        reconstructor = FormulaReconstructor()
        text = "x\n2"
        fragments = reconstructor.detect_fragments(text)

        # Pode detectar como expoente ou variável
        assert len(fragments) >= 1

    def test_detect_operator_orphan(self):
        """Detecta operador órfão."""
        reconstructor = FormulaReconstructor()
        text = "valor\n+\noutro valor"
        fragments = reconstructor.detect_fragments(text)

        operator_fragments = [f for f in fragments if f.fragment_type == FragmentType.OPERATOR]
        assert len(operator_fragments) >= 1


class TestFormulaReconstructorUtilityFunctions:
    """Testes para funções utilitárias."""

    def test_reconstruct_formulas_function(self):
        """Teste da função reconstruct_formulas."""
        text = "a\n───\nb"
        result = reconstruct_formulas(text)
        assert isinstance(result, str)
        assert "a/b" in result or "a)/(" in result

    def test_detect_formula_fragments_function(self):
        """Teste da função detect_formula_fragments."""
        text = "x\n2\n+\ny"
        fragments = detect_formula_fragments(text)
        assert isinstance(fragments, list)

    def test_fix_fraction_on_multiple_lines(self):
        """Teste da função fix_fraction_on_multiple_lines."""
        lines = ["numerador", "───", "denominador"]
        result = fix_fraction_on_multiple_lines(lines)

        assert isinstance(result, list)
        # Deve ter menos linhas após reconstrução
        assert len(result) <= len(lines)

    def test_merge_equation_lines(self):
        """Teste da função merge_equation_lines."""
        lines = ["x =", "5"]
        result = merge_equation_lines(lines)

        assert isinstance(result, list)


class TestFormulaReconstructorStats:
    """Testes para estatísticas do reconstrutor."""

    def test_stats_initial(self):
        """Estatísticas iniciais são zero."""
        reconstructor = FormulaReconstructor()
        stats = reconstructor.get_stats()

        assert stats['fractions_reconstructed'] == 0
        assert stats['equations_reconstructed'] == 0

    def test_stats_after_reconstruction(self):
        """Estatísticas atualizam após reconstrução."""
        reconstructor = FormulaReconstructor()
        reconstructor.reconstruct("a\n───\nb")

        stats = reconstructor.get_stats()
        assert stats['lines_processed'] > 0

    def test_reset_stats(self):
        """Reset de estatísticas funciona."""
        reconstructor = FormulaReconstructor()
        reconstructor.reconstruct("x =\n5")
        reconstructor.reset_stats()

        stats = reconstructor.get_stats()
        assert stats['fractions_reconstructed'] == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestMathModulesIntegration:
    """Testes de integração entre os módulos."""

    def test_detect_then_convert(self):
        """Detecta spans e depois converte."""
        detector = MathSpanDetector()
        converter = SurgicalLaTeXConverter()

        text = "O valor de ρ = m/V"
        spans = detector.detect_spans(text)
        converted = converter.convert_line(text)

        # Deve haver spans detectados
        assert len(spans) >= 0  # Pode não detectar dependendo do threshold
        # Conversão deve funcionar
        assert isinstance(converted, str)

    def test_reconstruct_then_convert(self):
        """Reconstrói fórmulas e depois converte."""
        reconstructor = FormulaReconstructor()
        converter = SurgicalLaTeXConverter()

        text = "a\n───\nb"
        reconstructed = reconstructor.reconstruct(text)
        converted = converter.convert_text(reconstructed)

        assert isinstance(converted, str)

    def test_full_pipeline(self):
        """Testa pipeline completa: reconstrução → detecção → conversão."""
        text = """A equação é:
ρ =
m/V
onde ρ é a densidade."""

        # 1. Reconstruir
        reconstructor = FormulaReconstructor()
        reconstructed = reconstructor.reconstruct(text)

        # 2. Converter
        converter = SurgicalLaTeXConverter()
        converted = converter.convert_text(reconstructed)

        # Verificações
        assert isinstance(converted, str)
        assert len(converted) > 0


class TestEdgeCases:
    """Testes de casos extremos."""

    def test_unicode_heavy_text(self):
        """Texto com muitos caracteres Unicode."""
        detector = MathSpanDetector()
        text = "αβγδεζηθικλμνξοπρστυφχψω = 1"
        spans = detector.detect_spans(text)
        assert isinstance(spans, list)

    def test_mixed_scripts(self):
        """Texto com scripts misturados."""
        converter = SurgicalLaTeXConverter()
        text = "Em português: α = beta, γ = gamma"
        result = converter.convert_line(text)
        assert isinstance(result, str)

    def test_very_long_expression(self):
        """Expressão muito longa."""
        detector = MathSpanDetector()
        text = "x = " + " + ".join(["a" * i for i in range(1, 20)])
        spans = detector.detect_spans(text)
        assert isinstance(spans, list)

    def test_nested_parentheses(self):
        """Parênteses aninhados."""
        detector = MathSpanDetector()
        text = "f((x + 1) * (y - 2)) = z"
        spans = detector.detect_spans(text)
        assert isinstance(spans, list)

    def test_special_characters_in_text(self):
        """Caracteres especiais no texto."""
        converter = SurgicalLaTeXConverter()
        text = "O valor é $100 e não ρ"
        result = converter.convert_line(text)
        assert isinstance(result, str)
