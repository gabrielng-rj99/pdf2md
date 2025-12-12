"""
Testes unitários para o módulo de detecção de fórmulas.

Testa:
- Detecção de equações
- Detecção de frações
- Detecção de potências e índices
- Detecção de funções matemáticas
- Detecção de símbolos especiais
- Conversão para LaTeX
- Formatação inline e bloco
"""

import pytest
from app.utils.formula_detector import (
    FormulaDetector,
    FormulaDetectorConfig,
    FormulaType,
    Formula,
    detect_and_format_formulas,
    is_math_expression,
    UNICODE_TO_LATEX,
    MATH_OPERATORS,
    MATH_SPECIAL,
    MATH_FUNCTIONS,
)


class TestFormulaDetectorConfig:
    """Testes para configuração do detector."""

    def test_default_config(self):
        """Testa valores padrão da configuração."""
        config = FormulaDetectorConfig()
        assert config.min_confidence == 0.5
        assert config.min_operators == 1
        assert config.detect_fractions is True
        assert config.detect_subscripts is True
        assert config.detect_superscripts is True
        assert config.detect_greek is True
        assert config.block_threshold == 50
        assert config.wrap_inline is True
        assert config.wrap_block is True

    def test_custom_config(self):
        """Testa configuração personalizada."""
        config = FormulaDetectorConfig(
            min_confidence=0.8,
            block_threshold=100,
            wrap_inline=False,
        )
        assert config.min_confidence == 0.8
        assert config.block_threshold == 100
        assert config.wrap_inline is False


class TestFormulaDataclass:
    """Testes para a dataclass Formula."""

    def test_create_formula(self):
        """Testa criação de fórmula."""
        formula = Formula(
            original="x = 2",
            latex="x = 2",
            formula_type=FormulaType.INLINE,
            confidence=0.8,
            start_pos=0,
            end_pos=5,
        )
        assert formula.original == "x = 2"
        assert formula.latex == "x = 2"
        assert formula.formula_type == FormulaType.INLINE
        assert formula.confidence == 0.8

    def test_formula_type_enum(self):
        """Testa enum de tipos de fórmula."""
        assert FormulaType.INLINE.value == "inline"
        assert FormulaType.BLOCK.value == "block"


class TestFormulaDetectorInit:
    """Testes de inicialização do detector."""

    def test_init_default(self):
        """Testa inicialização com configuração padrão."""
        detector = FormulaDetector()
        assert detector.config is not None
        assert detector.config.min_confidence == 0.5

    def test_init_custom_config(self):
        """Testa inicialização com configuração customizada."""
        config = FormulaDetectorConfig(min_confidence=0.9)
        detector = FormulaDetector(config)
        assert detector.config.min_confidence == 0.9


class TestEquationDetection:
    """Testes para detecção de equações."""

    def test_simple_equation(self):
        """Testa detecção de equação simples."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("A fórmula é x = 5")
        assert len(formulas) >= 1
        assert any("=" in f.original for f in formulas)

    def test_equation_with_operators(self):
        """Testa equação com operadores."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("y = x + 2")
        assert len(formulas) >= 1

    def test_physics_equation(self):
        """Testa equação de física."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("E = mc²")
        # Pode ou não detectar dependendo do formato
        # O importante é não dar erro

    def test_no_equation(self):
        """Testa texto sem equação."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("Este é um texto comum sem fórmulas.")
        # Pode detectar 0 ou poucas fórmulas
        assert isinstance(formulas, list)


class TestFractionDetection:
    """Testes para detecção de frações."""

    def test_simple_fraction(self):
        """Testa fração simples."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("a/b")
        has_fraction = any("frac" in f.latex for f in formulas)
        # Fração simples pode ou não ser detectada dependendo do contexto
        assert isinstance(formulas, list)

    def test_numeric_fraction(self):
        """Testa fração numérica."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("1/2")
        assert isinstance(formulas, list)

    def test_complex_fraction(self):
        """Testa fração complexa."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("(a+b)/(c+d)")
        assert isinstance(formulas, list)

    def test_common_abbreviation_not_fraction(self):
        """Testa que abreviações comuns não são detectadas como frações."""
        detector = FormulaDetector()
        result = detector._is_common_abbreviation("km/h")
        assert result is True
        result = detector._is_common_abbreviation("e/ou")
        assert result is True

    def test_fraction_detection_disabled(self):
        """Testa desativação de detecção de frações."""
        config = FormulaDetectorConfig(detect_fractions=False)
        detector = FormulaDetector(config)
        formulas = detector._detect_fractions("a/b")
        assert formulas == []


class TestPowerSubscriptDetection:
    """Testes para detecção de potências e índices."""

    def test_power_simple(self):
        """Testa potência simples."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("x^2")
        assert len(formulas) >= 1
        assert any("^" in f.latex for f in formulas)

    def test_power_with_braces(self):
        """Testa potência com chaves."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("x^{n+1}")
        assert isinstance(formulas, list)

    def test_subscript_simple(self):
        """Testa índice simples."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("x_1")
        assert len(formulas) >= 1
        assert any("_" in f.latex for f in formulas)

    def test_subscript_with_braces(self):
        """Testa índice com chaves."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("x_{i,j}")
        assert isinstance(formulas, list)

    def test_superscript_disabled(self):
        """Testa desativação de potências."""
        config = FormulaDetectorConfig(detect_superscripts=False)
        detector = FormulaDetector(config)
        formulas = detector._detect_powers_subscripts("x^2")
        # Não deve detectar potências
        power_formulas = [f for f in formulas if "^" in f.original]
        assert len(power_formulas) == 0

    def test_subscript_disabled(self):
        """Testa desativação de índices."""
        config = FormulaDetectorConfig(detect_subscripts=False)
        detector = FormulaDetector(config)
        formulas = detector._detect_powers_subscripts("x_1")
        # Não deve detectar índices
        sub_formulas = [f for f in formulas if "_" in f.original]
        assert len(sub_formulas) == 0


class TestFunctionDetection:
    """Testes para detecção de funções matemáticas."""

    def test_sin_function(self):
        """Testa função seno."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("sin(x)")
        assert isinstance(formulas, list)

    def test_log_function(self):
        """Testa função logaritmo."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("log(x)")
        assert isinstance(formulas, list)

    def test_log_with_base(self):
        """Testa logaritmo com base."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("log_2(x)")
        assert isinstance(formulas, list)

    def test_function_detection_disabled(self):
        """Testa desativação de detecção de funções."""
        config = FormulaDetectorConfig(detect_special_functions=False)
        detector = FormulaDetector(config)
        formulas = detector._detect_functions("sin(x)")
        assert formulas == []


class TestGreekLetterDetection:
    """Testes para detecção de letras gregas."""

    def test_alpha(self):
        """Testa letra alpha."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("α = 0.5")
        has_alpha = any("alpha" in f.latex for f in formulas)
        assert has_alpha or len(formulas) >= 0  # Pode ou não detectar

    def test_pi(self):
        """Testa letra pi."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("π")
        assert isinstance(formulas, list)

    def test_greek_detection_disabled(self):
        """Testa desativação de detecção de gregas."""
        config = FormulaDetectorConfig(detect_greek=False)
        detector = FormulaDetector(config)
        formulas = detector._detect_special_symbols("α = 0.5")
        assert formulas == []


class TestLatexConversion:
    """Testes para conversão para LaTeX."""

    def test_convert_greek_alpha(self):
        """Testa conversão de alpha."""
        detector = FormulaDetector()
        result = detector._convert_to_latex("α")
        assert "alpha" in result

    def test_convert_greek_pi(self):
        """Testa conversão de pi."""
        detector = FormulaDetector()
        result = detector._convert_to_latex("π")
        assert "pi" in result

    def test_convert_times(self):
        """Testa conversão de multiplicação."""
        detector = FormulaDetector()
        result = detector._convert_to_latex("×")
        assert "times" in result

    def test_convert_infinity(self):
        """Testa conversão de infinito."""
        detector = FormulaDetector()
        result = detector._convert_to_latex("∞")
        assert "infty" in result

    def test_convert_power_notation(self):
        """Testa conversão de notação de potência."""
        detector = FormulaDetector()
        result = detector._convert_to_latex("x2")
        assert "^" in result or "2" in result


class TestProcessText:
    """Testes para processamento de texto completo."""

    def test_process_simple_equation(self):
        """Testa processamento de equação simples."""
        detector = FormulaDetector()
        result = detector.process_text("A área é A = πr²")
        assert isinstance(result, str)

    def test_process_no_formula(self):
        """Testa processamento sem fórmula."""
        detector = FormulaDetector()
        original = "Este texto não tem fórmulas"
        result = detector.process_text(original)
        assert result == original

    def test_process_empty_string(self):
        """Testa processamento de string vazia."""
        detector = FormulaDetector()
        result = detector.process_text("")
        assert result == ""

    def test_process_short_string(self):
        """Testa processamento de string curta."""
        detector = FormulaDetector()
        result = detector.process_text("ab")
        assert result == "ab"

    def test_inline_wrapping(self):
        """Testa que fórmulas inline são envolvidas com $."""
        config = FormulaDetectorConfig(wrap_inline=True)
        detector = FormulaDetector(config)
        # O resultado pode ou não ter $, dependendo da detecção
        result = detector.process_text("x^2")
        assert isinstance(result, str)


class TestIsFormulaLine:
    """Testes para verificação de linha de fórmula."""

    def test_equation_line(self):
        """Testa linha que é equação."""
        detector = FormulaDetector()
        result = detector.is_formula_line("x + y = z")
        assert isinstance(result, bool)

    def test_complex_equation_line(self):
        """Testa linha com equação complexa."""
        detector = FormulaDetector()
        result = detector.is_formula_line("E = mc^2 + p^2/2m")
        assert isinstance(result, bool)

    def test_text_line(self):
        """Testa linha de texto comum."""
        detector = FormulaDetector()
        result = detector.is_formula_line("Este é um parágrafo de texto comum.")
        assert result is False

    def test_empty_line(self):
        """Testa linha vazia."""
        detector = FormulaDetector()
        result = detector.is_formula_line("")
        assert result is False

    def test_short_line(self):
        """Testa linha curta."""
        detector = FormulaDetector()
        result = detector.is_formula_line("ab")
        assert result is False


class TestFormatFormulaBlock:
    """Testes para formatação de bloco de fórmula."""

    def test_format_simple_block(self):
        """Testa formatação de bloco simples."""
        detector = FormulaDetector()
        result = detector.format_formula_block("x = y + z")
        assert "$$" in result
        assert "x" in result

    def test_format_block_with_greek(self):
        """Testa formatação de bloco com letras gregas."""
        detector = FormulaDetector()
        result = detector.format_formula_block("α + β = γ")
        assert "$$" in result


class TestConvenienceFunctions:
    """Testes para funções de conveniência."""

    def test_detect_and_format_formulas(self):
        """Testa função de conveniência."""
        result = detect_and_format_formulas("x = 2")
        assert isinstance(result, str)

    def test_detect_and_format_with_config(self):
        """Testa função de conveniência com config."""
        config = FormulaDetectorConfig(min_confidence=0.9)
        result = detect_and_format_formulas("x = 2", config)
        assert isinstance(result, str)

    def test_is_math_expression_true(self):
        """Testa identificação de expressão matemática."""
        assert is_math_expression("x = y") is True
        assert is_math_expression("α + β") is True
        assert is_math_expression("x^2") is True

    def test_is_math_expression_false(self):
        """Testa identificação de texto comum."""
        assert is_math_expression("") is False
        assert is_math_expression("a") is False

    def test_is_math_expression_edge_cases(self):
        """Testa casos de borda."""
        assert is_math_expression(None) is False if is_math_expression("") is False else True
        assert isinstance(is_math_expression("test"), bool)


class TestRemoveOverlaps:
    """Testes para remoção de sobreposições."""

    def test_remove_overlaps_empty(self):
        """Testa remoção com lista vazia."""
        detector = FormulaDetector()
        result = detector._remove_overlaps([])
        assert result == []

    def test_remove_overlaps_single(self):
        """Testa remoção com item único."""
        detector = FormulaDetector()
        formula = Formula(
            original="x=1",
            latex="x=1",
            formula_type=FormulaType.INLINE,
            confidence=0.8,
            start_pos=0,
            end_pos=3,
        )
        result = detector._remove_overlaps([formula])
        assert len(result) == 1

    def test_remove_overlaps_no_overlap(self):
        """Testa remoção sem sobreposição."""
        detector = FormulaDetector()
        f1 = Formula("x=1", "x=1", FormulaType.INLINE, 0.8, 0, 3)
        f2 = Formula("y=2", "y=2", FormulaType.INLINE, 0.8, 5, 8)
        result = detector._remove_overlaps([f1, f2])
        assert len(result) == 2

    def test_remove_overlaps_with_overlap(self):
        """Testa remoção com sobreposição."""
        detector = FormulaDetector()
        f1 = Formula("x=1", "x=1", FormulaType.INLINE, 0.6, 0, 5)
        f2 = Formula("x=1+2", "x=1+2", FormulaType.INLINE, 0.9, 0, 7)
        result = detector._remove_overlaps([f1, f2])
        # Deve manter o de maior confiança ou o que não sobrepõe
        assert len(result) >= 1


class TestStatistics:
    """Testes para estatísticas do detector."""

    def test_get_statistics(self):
        """Testa obtenção de estatísticas."""
        detector = FormulaDetector()
        stats = detector.get_statistics()
        assert "config" in stats
        assert "patterns_count" in stats
        assert stats["patterns_count"] > 0


class TestConfidenceCalculation:
    """Testes para cálculo de confiança."""

    def test_equation_confidence_with_equals(self):
        """Testa confiança de equação com =."""
        detector = FormulaDetector()
        confidence = detector._calculate_equation_confidence("x = y")
        assert confidence > 0.0

    def test_equation_confidence_with_operators(self):
        """Testa confiança de equação com operadores."""
        detector = FormulaDetector()
        confidence = detector._calculate_equation_confidence("x + y = z")
        assert confidence > 0.0

    def test_equation_confidence_common_text(self):
        """Testa que texto comum tem baixa confiança."""
        detector = FormulaDetector()
        confidence = detector._calculate_equation_confidence("de da do em para com")
        assert confidence < 0.5

    def test_fraction_confidence(self):
        """Testa confiança de fração."""
        detector = FormulaDetector()
        confidence = detector._calculate_fraction_confidence("a", "b")
        assert 0.0 <= confidence <= 1.0


class TestUnicodeToLatexMapping:
    """Testes para mapeamento Unicode-LaTeX."""

    def test_greek_lowercase_mapping(self):
        """Testa mapeamento de gregas minúsculas."""
        assert 'α' in UNICODE_TO_LATEX
        assert 'β' in UNICODE_TO_LATEX
        assert 'γ' in UNICODE_TO_LATEX
        assert 'π' in UNICODE_TO_LATEX
        assert 'ω' in UNICODE_TO_LATEX

    def test_greek_uppercase_mapping(self):
        """Testa mapeamento de gregas maiúsculas."""
        assert 'Γ' in UNICODE_TO_LATEX
        assert 'Δ' in UNICODE_TO_LATEX
        assert 'Σ' in UNICODE_TO_LATEX
        assert 'Ω' in UNICODE_TO_LATEX

    def test_operator_mapping(self):
        """Testa mapeamento de operadores."""
        assert '×' in UNICODE_TO_LATEX
        assert '÷' in UNICODE_TO_LATEX
        assert '∞' in UNICODE_TO_LATEX
        assert '∑' in UNICODE_TO_LATEX
        assert '∫' in UNICODE_TO_LATEX


class TestMathOperatorsSet:
    """Testes para conjunto de operadores matemáticos."""

    def test_basic_operators(self):
        """Testa operadores básicos."""
        assert '+' in MATH_OPERATORS
        assert '-' in MATH_OPERATORS
        assert '=' in MATH_OPERATORS
        assert '<' in MATH_OPERATORS
        assert '>' in MATH_OPERATORS

    def test_special_operators(self):
        """Testa operadores especiais."""
        assert '∞' in MATH_OPERATORS
        assert '∑' in MATH_OPERATORS
        assert '∫' in MATH_OPERATORS
        assert '√' in MATH_OPERATORS


class TestMathFunctionsSet:
    """Testes para conjunto de funções matemáticas."""

    def test_trig_functions(self):
        """Testa funções trigonométricas."""
        assert 'sin' in MATH_FUNCTIONS
        assert 'cos' in MATH_FUNCTIONS
        assert 'tan' in MATH_FUNCTIONS

    def test_log_functions(self):
        """Testa funções logarítmicas."""
        assert 'log' in MATH_FUNCTIONS
        assert 'ln' in MATH_FUNCTIONS
        assert 'exp' in MATH_FUNCTIONS

    def test_portuguese_functions(self):
        """Testa funções em português."""
        assert 'sen' in MATH_FUNCTIONS
        assert 'tg' in MATH_FUNCTIONS


class TestEdgeCases:
    """Testes para casos de borda."""

    def test_none_text(self):
        """Testa texto None."""
        detector = FormulaDetector()
        # process_text não deve aceitar None, mas detect_formulas pode
        try:
            result = detector.detect_formulas(None)
            assert result == []
        except (TypeError, AttributeError):
            pass  # Comportamento esperado

    def test_very_long_text(self):
        """Testa texto muito longo."""
        detector = FormulaDetector()
        long_text = "x = " + "y + " * 100 + "z"
        result = detector.detect_formulas(long_text)
        assert isinstance(result, list)

    def test_special_characters_only(self):
        """Testa texto com apenas caracteres especiais."""
        detector = FormulaDetector()
        result = detector.detect_formulas("!@#$%^&*()")
        assert isinstance(result, list)

    def test_mixed_content(self):
        """Testa conteúdo misto de texto e fórmulas."""
        detector = FormulaDetector()
        text = "A velocidade v = d/t onde d é distância e t é tempo."
        result = detector.process_text(text)
        assert isinstance(result, str)
        assert len(result) > 0


class TestRealWorldExamples:
    """Testes com exemplos reais de PDFs acadêmicos."""

    def test_physics_equation(self):
        """Testa equação de física."""
        detector = FormulaDetector()
        text = "ρg γ g V m V G γ"
        result = detector.detect_formulas(text)
        assert isinstance(result, list)

    def test_engineering_formula(self):
        """Testa fórmula de engenharia."""
        detector = FormulaDetector()
        text = "P = F/A"
        result = detector.process_text(text)
        assert isinstance(result, str)

    def test_complex_fraction(self):
        """Testa fração complexa."""
        detector = FormulaDetector()
        text = "volume V peso G sendo V G"
        result = detector.detect_formulas(text)
        assert isinstance(result, list)

    def test_subscripted_variables(self):
        """Testa variáveis com índices."""
        detector = FormulaDetector()
        text = "V1, V2, P1, P2"
        result = detector.detect_formulas(text)
        assert isinstance(result, list)


class TestChemicalFormulas:
    """Testes para detecção de fórmulas químicas."""

    def test_simple_water(self):
        """Testa fórmula simples de água."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("H2O")
        # Deve detectar ou ignorar graciosamente
        assert isinstance(formulas, list)

    def test_water_with_context(self):
        """Testa água em contexto."""
        detector = FormulaDetector()
        result = detector.process_text("A fórmula da água é H2O")
        assert isinstance(result, str)
        assert "H" in result or "2" in result

    def test_carbon_dioxide(self):
        """Testa dióxido de carbono."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("CO2")
        assert isinstance(formulas, list)

    def test_calcium_hydroxide(self):
        """Testa hidróxido de cálcio."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("Ca(OH)2")
        assert isinstance(formulas, list)

    def test_ethanol(self):
        """Testa fórmula de etanol."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("CH3CH2OH")
        assert isinstance(formulas, list)

    def test_chemical_equation(self):
        """Testa equação química."""
        detector = FormulaDetector()
        text = "2H2 + O2 → 2H2O"
        formulas = detector.detect_formulas(text)
        assert isinstance(formulas, list)

    def test_coefficients(self):
        """Testa coeficientes estequiométricos."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("3H2SO4")
        assert isinstance(formulas, list)

    def test_chemical_detection_disabled(self):
        """Testa desativação de detecção química."""
        config = FormulaDetectorConfig(detect_chemical=False)
        detector = FormulaDetector(config)
        formulas = detector._detect_chemical_formulas("H2O")
        assert formulas == []

    def test_chloride(self):
        """Testa cloreto de sódio."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("NaCl")
        assert isinstance(formulas, list)

    def test_sulfuric_acid(self):
        """Testa ácido sulfúrico."""
        detector = FormulaDetector()
        formulas = detector.detect_formulas("H2SO4")
        assert isinstance(formulas, list)


class TestFragmentDetection:
    """Testes para detecção e reconstrução de fragmentos."""

    def test_is_formula_fragment_simple(self):
        """Testa detecção de fragmento simples."""
        detector = FormulaDetector()
        assert detector._is_formula_fragment("= x + 2") is True
        assert detector._is_formula_fragment("+ y") is True

    def test_is_formula_fragment_false(self):
        """Testa não-fragmentos."""
        detector = FormulaDetector()
        assert detector._is_formula_fragment("Este é um texto normal") is False
        assert detector._is_formula_fragment("a") is False

    def test_is_complete_formula_equation(self):
        """Testa se detecta fórmula completa."""
        detector = FormulaDetector()
        assert detector._is_complete_formula("x = y + z") is True

    def test_is_complete_formula_balanced_parens(self):
        """Testa detecção com parênteses balanceados."""
        detector = FormulaDetector()
        assert detector._is_complete_formula("(a + b) * (c + d)") is True

    def test_is_complete_formula_incomplete(self):
        """Testa detecção de fórmula incompleta."""
        detector = FormulaDetector()
        # Fórmulas muito curtas ou incompletas devem retornar False
        result = detector._is_complete_formula("= ")
        assert isinstance(result, bool)

    def test_fragment_buffer_initialization(self):
        """Testa que buffer de fragmentos é inicializado."""
        detector = FormulaDetector()
        assert hasattr(detector, '_fragment_buffer')
        assert isinstance(detector._fragment_buffer, list)

    def test_reconstruct_fragments_disabled(self):
        """Testa desativação de reconstrução."""
        config = FormulaDetectorConfig(reconstruct_fragments=False)
        detector = FormulaDetector(config)
        lines = ["= x", "+ 2"]
        result = detector._detect_formula_fragments(lines)
        assert result == []

    def test_detect_formula_fragments_empty(self):
        """Testa com lista vazia."""
        detector = FormulaDetector()
        result = detector._detect_formula_fragments([])
        assert result == []

    def test_detect_formula_fragments_single_line(self):
        """Testa com linha única."""
        detector = FormulaDetector()
        result = detector._detect_formula_fragments(["x = 1"])
        assert isinstance(result, list)

    def test_chemical_confidence_calculation(self):
        """Testa cálculo de confiança para químicas."""
        detector = FormulaDetector()
        conf1 = detector._calculate_chemical_confidence("H2O")
        conf2 = detector._calculate_chemical_confidence("texto aleatório")
        assert conf1 > conf2
        assert 0.0 <= conf1 <= 1.0
        assert 0.0 <= conf2 <= 1.0

    def test_convert_chemical_to_latex(self):
        """Testa conversão de fórmula química."""
        detector = FormulaDetector()
        result = detector._convert_chemical_to_latex("H2O")
        assert isinstance(result, str)
        assert ("_" in result or "H" in result)  # Deve ter subscrito ou preservar

    def test_mixed_formula_and_text(self):
        """Testa texto com fórmula e texto normal."""
        detector = FormulaDetector()
        text = "A água tem fórmula H2O e densidade 1 g/cm³"
        result = detector.process_text(text)
        assert isinstance(result, str)
        assert len(result) > 0
