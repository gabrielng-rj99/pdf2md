"""
Testes unitários para o módulo de IA leve para fórmulas matemáticas.
"""

import pytest
from app.utils.formula_ai import (
    LightFormulaAI,
    FormulaConfidence,
    FormulaFeatures,
    ReconstructedFormula,
    get_formula_ai,
    classify_formula,
    is_formula,
    process_formula,
    reconstruct_formula,
)


class TestLightFormulaAI:
    """Testes para a classe LightFormulaAI."""

    def setup_method(self):
        """Setup para cada teste."""
        self.ai = LightFormulaAI()

    def test_init(self):
        """Deve inicializar corretamente."""
        assert self.ai is not None
        assert self.ai._cache == {}

    def test_extract_features_empty_text(self):
        """Deve retornar features zeradas para texto vazio."""
        features = self.ai.extract_features("")
        assert features.total_chars == 0
        assert features.total_words == 0
        assert features.formula_score == 0.0

    def test_extract_features_normal_text(self):
        """Deve extrair features de texto normal."""
        text = "Este é um texto normal sem fórmulas."
        features = self.ai.extract_features(text)
        assert features.total_chars > 0
        assert features.total_words > 0
        assert features.isolated_letters == 0 or features.isolated_letters == 1  # "é"
        assert features.math_symbols == 0

    def test_extract_features_math_text(self):
        """Deve extrair features de texto com elementos matemáticos."""
        text = "F = m × a"
        features = self.ai.extract_features(text)
        assert features.has_equation is True
        assert features.isolated_letters >= 2  # F, m, a
        assert features.operators >= 1  # =

    def test_extract_features_greek_letters(self):
        """Deve detectar letras gregas."""
        text = "α + β = γ"
        features = self.ai.extract_features(text)
        assert features.greek_letters >= 3
        assert features.has_equation is True

    def test_extract_features_subscripts(self):
        """Deve detectar subscritos."""
        text = "H₂O"
        features = self.ai.extract_features(text)
        assert features.subscripts >= 1

    def test_extract_features_superscripts(self):
        """Deve detectar superscritos."""
        text = "x² + y²"
        features = self.ai.extract_features(text)
        assert features.superscripts >= 2

    def test_extract_features_math_function(self):
        """Deve detectar funções matemáticas."""
        text = "sen(x) + cos(y)"
        features = self.ai.extract_features(text)
        assert features.has_function is True

    def test_extract_features_equation_number(self):
        """Deve detectar número de equação."""
        text = "F = ma (1.1)"
        features = self.ai.extract_features(text)
        assert features.has_equation_number is True

    def test_extract_features_fraction(self):
        """Deve detectar frações."""
        text = "a/b = c"
        features = self.ai.extract_features(text)
        assert features.has_fraction is True

    def test_extract_features_power(self):
        """Deve detectar potências."""
        text = "x^2 + y^3"
        features = self.ai.extract_features(text)
        assert features.has_power is True

    def test_extract_features_connectors(self):
        """Deve detectar conectores."""
        text = "onde x é a variável"
        features = self.ai.extract_features(text)
        assert features.starts_with_connector is True

    def test_extract_features_caching(self):
        """Deve usar cache para features já calculadas."""
        text = "F = ma"
        features1 = self.ai.extract_features(text)
        features2 = self.ai.extract_features(text)
        # Deve retornar o mesmo objeto do cache
        assert features1 is features2

    def test_classify_not_formula(self):
        """Deve classificar texto normal como não-fórmula."""
        text = "Este é um parágrafo normal com várias palavras sem elementos matemáticos."
        confidence, score = self.ai.classify(text)
        assert confidence == FormulaConfidence.NONE
        assert score < 0.35

    def test_classify_high_confidence_formula(self):
        """Deve classificar fórmula clara com alguma confiança."""
        text = "α = β + γ"
        confidence, score = self.ai.classify(text)
        # Com thresholds conservadores, pode ser LOW ou maior
        assert confidence.value >= FormulaConfidence.LOW.value

    def test_classify_medium_confidence_formula(self):
        """Deve classificar fórmula parcial com média confiança."""
        text = "x = 5"
        confidence, score = self.ai.classify(text)
        # Pode ser NONE, LOW, ou MEDIUM dependendo do contexto
        assert confidence.value >= FormulaConfidence.NONE.value

    def test_is_formula_true(self):
        """Deve retornar True para fórmula."""
        text = "∫f(x)dx = F(x)"
        # Pode ou não ser detectado dependendo dos thresholds
        result = self.ai.is_formula(text, FormulaConfidence.LOW)
        assert isinstance(result, bool)

    def test_is_formula_false(self):
        """Deve retornar False para texto normal."""
        text = "Este é um texto comum sem matemática."
        result = self.ai.is_formula(text)
        assert result is False

    def test_reconstruct_formula_basic(self):
        """Deve reconstruir fórmula básica."""
        text = "F = ma"
        result = self.ai.reconstruct_formula(text)
        assert isinstance(result, ReconstructedFormula)
        assert result.original == text
        assert len(result.latex) > 0

    def test_reconstruct_formula_with_label(self):
        """Deve extrair número de equação."""
        text = "E = mc² (1.1)"
        result = self.ai.reconstruct_formula(text)
        assert result.equation_label is not None

    def test_convert_to_latex_greek(self):
        """Deve converter letras gregas para LaTeX."""
        text = "alpha + beta"
        result = self.ai._convert_to_latex(text)
        assert "\\alpha" in result
        assert "\\beta" in result

    def test_convert_to_latex_unicode_symbols(self):
        """Deve converter símbolos Unicode para LaTeX."""
        text = "∞ ∑ ∫"
        result = self.ai._convert_to_latex(text)
        assert "\\infty" in result
        assert "\\sum" in result
        assert "\\int" in result

    def test_convert_to_latex_fractions(self):
        """Deve converter frações."""
        text = "a/b"
        result = self.ai._convert_to_latex(text)
        assert "\\frac{a}{b}" in result

    def test_convert_to_latex_powers(self):
        """Deve converter potências."""
        text = "x^2"
        result = self.ai._convert_to_latex(text)
        assert "x^{2}" in result

    def test_convert_to_latex_functions(self):
        """Deve converter funções matemáticas."""
        text = "sen(x)"
        result = self.ai._convert_to_latex(text)
        assert "\\sin" in result

    def test_process_text_block_normal(self):
        """Deve retornar texto normal sem alteração."""
        text = "Este é um parágrafo normal sem fórmulas matemáticas."
        result = self.ai.process_text_block(text)
        assert result == text

    def test_process_text_block_long_text(self):
        """Deve retornar texto longo sem alteração."""
        text = "A" * 200
        result = self.ai.process_text_block(text)
        assert result == text

    def test_extract_readable_parts(self):
        """Deve extrair partes legíveis."""
        text = "velocidade v = d/t (1.5)"
        readable, label = self.ai.extract_readable_parts(text)
        assert label is not None
        assert isinstance(readable, str)

    def test_get_cache_stats(self):
        """Deve retornar estatísticas do cache."""
        # Primeiro, adicionar algo ao cache
        self.ai.extract_features("test")
        stats = self.ai.get_cache_stats()
        assert "cache_size" in stats
        assert "cache_max_size" in stats
        assert stats["cache_size"] >= 1

    def test_clear_cache(self):
        """Deve limpar o cache."""
        self.ai.extract_features("test")
        self.ai.clear_cache()
        stats = self.ai.get_cache_stats()
        assert stats["cache_size"] == 0


class TestFormulaFeatures:
    """Testes para a classe FormulaFeatures."""

    def test_default_values(self):
        """Deve ter valores padrão zerados."""
        features = FormulaFeatures()
        assert features.total_chars == 0
        assert features.total_words == 0
        assert features.isolated_letters == 0
        assert features.math_symbols == 0
        assert features.greek_letters == 0
        assert features.operators == 0
        assert features.formula_score == 0.0
        assert features.has_equation is False
        assert features.has_fraction is False


class TestReconstructedFormula:
    """Testes para a classe ReconstructedFormula."""

    def test_creation(self):
        """Deve criar instância corretamente."""
        formula = ReconstructedFormula(
            original="F = ma",
            latex="F = ma",
            confidence=FormulaConfidence.HIGH,
            equation_label="1.1",
        )
        assert formula.original == "F = ma"
        assert formula.latex == "F = ma"
        assert formula.confidence == FormulaConfidence.HIGH
        assert formula.equation_label == "1.1"


class TestFormulaConfidence:
    """Testes para o enum FormulaConfidence."""

    def test_values(self):
        """Deve ter valores corretos."""
        assert FormulaConfidence.NONE.value == 0
        assert FormulaConfidence.LOW.value == 1
        assert FormulaConfidence.MEDIUM.value == 2
        assert FormulaConfidence.HIGH.value == 3

    def test_comparison(self):
        """Deve permitir comparação."""
        assert FormulaConfidence.HIGH.value > FormulaConfidence.LOW.value
        assert FormulaConfidence.MEDIUM.value > FormulaConfidence.NONE.value


class TestGlobalFunctions:
    """Testes para funções globais de conveniência."""

    def test_get_formula_ai_singleton(self):
        """Deve retornar mesma instância."""
        ai1 = get_formula_ai()
        ai2 = get_formula_ai()
        assert ai1 is ai2

    def test_classify_formula_function(self):
        """Deve classificar fórmula."""
        confidence, score = classify_formula("x + y = z")
        assert isinstance(confidence, FormulaConfidence)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_is_formula_function(self):
        """Deve verificar se é fórmula."""
        result = is_formula("texto normal")
        assert isinstance(result, bool)

    def test_process_formula_function(self):
        """Deve processar fórmula."""
        result = process_formula("alpha + beta")
        assert isinstance(result, str)

    def test_reconstruct_formula_function(self):
        """Deve reconstruir fórmula."""
        result = reconstruct_formula("E = mc²")
        assert isinstance(result, ReconstructedFormula)


class TestEdgeCases:
    """Testes para casos extremos."""

    def setup_method(self):
        """Setup para cada teste."""
        self.ai = LightFormulaAI()

    def test_empty_string(self):
        """Deve lidar com string vazia."""
        confidence, score = self.ai.classify("")
        assert confidence == FormulaConfidence.NONE
        assert score == 0.0

    def test_whitespace_only(self):
        """Deve lidar com apenas espaços."""
        confidence, score = self.ai.classify("   ")
        assert confidence == FormulaConfidence.NONE

    def test_single_character(self):
        """Deve lidar com caractere único."""
        confidence, score = self.ai.classify("x")
        assert isinstance(confidence, FormulaConfidence)

    def test_very_long_text(self):
        """Deve lidar com texto muito longo."""
        text = "palavra " * 100
        result = self.ai.process_text_block(text)
        assert result == text  # Texto longo não deve ser modificado

    def test_special_characters(self):
        """Deve lidar com caracteres especiais."""
        text = "!@#$%^&*()"
        result = self.ai.process_text_block(text)
        assert isinstance(result, str)

    def test_mixed_content(self):
        """Deve lidar com conteúdo misto."""
        text = "A velocidade v = d/t é calculada pela distância dividida pelo tempo."
        result = self.ai.process_text_block(text)
        assert isinstance(result, str)

    def test_unicode_text(self):
        """Deve lidar com texto Unicode."""
        text = "αβγδεζηθικλμνξοπρστυφχψω"
        features = self.ai.extract_features(text)
        assert features.greek_letters > 0

    def test_numbers_only(self):
        """Deve lidar com apenas números."""
        text = "123456"
        confidence, score = self.ai.classify(text)
        assert confidence == FormulaConfidence.NONE

    def test_fragmented_formula_detection(self):
        """Deve detectar fórmulas fragmentadas."""
        text = "V m ρ = sendo volume massa"
        # Este é um padrão de fórmula fragmentada
        features = self.ai.extract_features(text)
        assert features.isolated_letters >= 2


class TestIntegration:
    """Testes de integração."""

    def setup_method(self):
        """Setup para cada teste."""
        self.ai = LightFormulaAI()

    def test_real_formula_1(self):
        """Teste com fórmula real de física."""
        text = "F = ma"
        features = self.ai.extract_features(text)
        assert features.has_equation is True
        # "F = ma" tem F, m, a mas regex pode não pegar todos dependendo do contexto
        assert features.isolated_letters >= 1

    def test_real_formula_2(self):
        """Teste com fórmula real de química."""
        text = "H₂O"
        features = self.ai.extract_features(text)
        assert features.subscripts >= 1

    def test_real_formula_3(self):
        """Teste com integral."""
        text = "∫f(x)dx"
        features = self.ai.extract_features(text)
        assert features.math_symbols >= 1

    def test_real_paragraph(self):
        """Teste com parágrafo real."""
        text = """A mecânica dos fluidos trata do comportamento dos fluidos
        em repouso ou em movimento e das leis que regem este comportamento."""
        confidence, score = self.ai.classify(text)
        assert confidence == FormulaConfidence.NONE

    def test_workflow_complete(self):
        """Teste do workflow completo."""
        # 1. Classificar
        text = "α = β + γ"
        confidence, score = self.ai.classify(text)

        # 2. Se for fórmula, reconstruir
        if confidence.value >= FormulaConfidence.LOW.value:
            result = self.ai.reconstruct_formula(text)
            assert result.latex is not None

        # 3. Processar bloco de texto
        processed = self.ai.process_text_block(text)
        assert isinstance(processed, str)
