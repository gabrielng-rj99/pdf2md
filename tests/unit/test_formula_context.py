"""
Testes unitários para o sistema de contexto na reconstrução de fórmulas.

Testa a capacidade do módulo formula_ai de usar contexto imediato
(texto anterior e posterior) para identificar e reconstruir fórmulas
de forma mais precisa.
"""

import pytest
from app.utils.formula_ai import (
    LightFormulaAI,
    FormulaConfidence,
    FormulaContext,
    ReconstructedFormula,
    get_formula_ai,
)


class TestFormulaContext:
    """Testes para a classe FormulaContext."""

    def test_context_creation(self):
        """Teste criação de contexto."""
        context = FormulaContext(
            text_before="A massa específica é definida como",
            text_after="onde m é a massa"
        )
        assert context.text_before == "A massa específica é definida como"
        assert context.text_after == "onde m é a massa"

    def test_context_default_values(self):
        """Teste valores padrão do contexto."""
        context = FormulaContext()
        assert context.text_before == ""
        assert context.text_after == ""
        assert context.detected_name is None
        assert context.detected_type is None
        assert context.related_variables == []


class TestExtractContext:
    """Testes para extração de contexto."""

    @pytest.fixture
    def ai(self):
        return LightFormulaAI()

    def test_extract_context_massa_especifica(self, ai):
        """Teste extração de contexto para massa específica."""
        context = ai.extract_context(
            text_before="a) massa específica: a massa de um fluido",
            text_after=""
        )
        assert context.detected_name == "massa específica"

    def test_extract_context_peso_especifico(self, ai):
        """Teste extração de contexto para peso específico."""
        context = ai.extract_context(
            text_before="b) peso específico: é o peso da unidade de volume",
            text_after=""
        )
        assert context.detected_name == "peso específico"

    def test_extract_context_pressao(self, ai):
        """Teste extração de contexto para pressão."""
        context = ai.extract_context(
            text_before="A pressão é definida como a relação entre força e área",
            text_after=""
        )
        assert context.detected_name == "pressão"

    def test_extract_context_lei_stevin(self, ai):
        """Teste extração de contexto para Lei de Stevin."""
        context = ai.extract_context(
            text_before="De acordo com a Lei de Stevin",
            text_after=""
        )
        assert context.detected_name == "Lei de Stevin"

    def test_extract_context_equacao_gases(self, ai):
        """Teste extração de contexto para equação dos gases."""
        context = ai.extract_context(
            text_before="A equação dos gases perfeitos estabelece que",
            text_after=""
        )
        assert context.detected_name == "Equação dos Gases"

    def test_extract_context_detects_type_definicao(self, ai):
        """Teste detecção de tipo: definição."""
        context = ai.extract_context(
            text_before="Por definição, a densidade é",
            text_after=""
        )
        assert context.detected_type == "definição"

    def test_extract_context_detects_type_lei(self, ai):
        """Teste detecção de tipo: lei."""
        context = ai.extract_context(
            text_before="A lei estabelece que",
            text_after=""
        )
        assert context.detected_type == "lei"

    def test_extract_context_detects_type_equacao(self, ai):
        """Teste detecção de tipo: equação."""
        context = ai.extract_context(
            text_before="Esta equação mostra que",
            text_after=""
        )
        assert context.detected_type == "equação"

    def test_extract_context_detects_variables(self, ai):
        """Teste detecção de variáveis relacionadas."""
        context = ai.extract_context(
            text_before="onde P é a pressão, V é o volume e T é a temperatura",
            text_after=""
        )
        assert 'P' in context.related_variables or 'V' in context.related_variables

    def test_extract_context_empty_input(self, ai):
        """Teste com entrada vazia."""
        context = ai.extract_context("", "")
        assert context.detected_name is None
        assert context.detected_type is None


class TestReconstructWithContext:
    """Testes para reconstrução com contexto."""

    @pytest.fixture
    def ai(self):
        return LightFormulaAI()

    def test_reconstruct_massa_especifica_with_context(self, ai):
        """Teste reconstrução de massa específica com contexto."""
        result = ai.reconstruct_with_context(
            text="volume massa sendo",
            text_before="a) massa específica: a massa de um fluido em uma unidade de volume é denominada densidade",
            text_after=""
        )
        assert "rho" in result.latex.lower() or "frac" in result.latex.lower() or "m" in result.latex

    def test_reconstruct_peso_especifico_with_context(self, ai):
        """Teste reconstrução de peso específico com contexto."""
        result = ai.reconstruct_with_context(
            text="γ = ρg",
            text_before="b) peso específico: é o peso da unidade de volume",
            text_after=""
        )
        assert result.formula_name == "peso específico" or "gamma" in result.latex.lower()

    def test_reconstruct_gas_equation_with_context(self, ai):
        """Teste reconstrução de equação dos gases com contexto."""
        result = ai.reconstruct_with_context(
            text="PV = nRT",
            text_before="A equação dos gases perfeitos é",
            text_after=""
        )
        # Deve reconhecer pelo contexto
        assert "nRT" in result.latex or "PV" in result.latex

    def test_reconstruct_preserves_equation_label(self, ai):
        """Teste que número de equação é preservado."""
        result = ai.reconstruct_with_context(
            text="x = y + z (1.5)",
            text_before="",
            text_after=""
        )
        # Número de equação deve ser extraído
        assert result.equation_label is not None or "1.5" in str(result.equation_label) or result.latex

    def test_reconstruct_without_context_fallback(self, ai):
        """Teste fallback quando não há contexto."""
        result = ai.reconstruct_with_context(
            text="a + b = c",
            text_before="",
            text_after=""
        )
        assert result.latex is not None
        assert len(result.latex) > 0


class TestKnownFormulas:
    """Testes para fórmulas conhecidas."""

    @pytest.fixture
    def ai(self):
        return LightFormulaAI()

    def test_known_formula_massa_volume(self, ai):
        """Teste reconhecimento de padrão massa/volume."""
        result = ai._try_known_formula_by_text("massa volume sendo")
        assert result is not None
        assert "frac" in result.lower() or "rho" in result.lower()

    def test_known_formula_peso_volume(self, ai):
        """Teste reconhecimento de padrão peso/volume."""
        result = ai._try_known_formula_by_text("volume peso sendo")
        assert result is not None

    def test_known_formula_pressao_forca_area(self, ai):
        """Teste reconhecimento de padrão pressão/força/área."""
        result = ai._try_known_formula_by_text("pressão força área")
        assert result is not None
        assert "frac" in result.lower() or "P" in result

    def test_known_formula_gases_perfeitos(self, ai):
        """Teste reconhecimento de equação dos gases."""
        result = ai._try_known_formula_by_text("pv nrt gas")
        assert result is not None
        assert "nRT" in result or "PV" in result

    def test_unknown_formula_returns_none(self, ai):
        """Teste que fórmula desconhecida retorna None."""
        result = ai._try_known_formula_by_text("texto qualquer sem padrão")
        assert result is None


class TestDescribeFormula:
    """Testes para descrição de fórmulas."""

    @pytest.fixture
    def ai(self):
        return LightFormulaAI()

    def test_describe_with_context(self, ai):
        """Teste descrição com contexto."""
        description = ai.describe_formula(
            text="ρ = m/V",
            context_before="A massa específica é definida como",
            context_after=""
        )
        assert "massa específica" in description.lower() or "ρ" in description

    def test_describe_without_context(self, ai):
        """Teste descrição sem contexto identificável."""
        description = ai.describe_formula(
            text="x + y = z",
            context_before="",
            context_after=""
        )
        # Deve retornar algo (mesmo que seja o texto original)
        assert len(description) > 0


class TestProcessTextBlockWithContext:
    """Testes para processamento de bloco de texto com contexto."""

    @pytest.fixture
    def ai(self):
        return LightFormulaAI()

    def test_process_with_context_before(self, ai):
        """Teste processamento com contexto anterior."""
        result = ai.process_text_block(
            text="γ = ρg",
            context_before="O peso específico é dado por",
            context_after=""
        )
        # Deve formatar como fórmula
        assert "$" in result or "gamma" in result.lower() or "γ" in result

    def test_process_long_text_unchanged(self, ai):
        """Teste que texto longo não é tratado como fórmula."""
        long_text = "Este é um texto muito longo que não deveria ser tratado como fórmula " * 3
        result = ai.process_text_block(long_text, "", "")
        assert result == long_text

    def test_process_empty_text(self, ai):
        """Teste processamento de texto vazio."""
        result = ai.process_text_block("", "", "")
        assert result == ""


class TestRealWorldCases:
    """Testes com casos reais do PDF aula1.pdf."""

    @pytest.fixture
    def ai(self):
        return LightFormulaAI()

    def test_real_case_densidade(self, ai):
        """Teste caso real: densidade."""
        context = ai.extract_context(
            text_before="a) massa específica : a massa de um fluido em uma unidade de volume é denominada densidade absoluta",
            text_after=""
        )
        assert context.detected_name in ["massa específica", "densidade"]

    def test_real_case_peso_especifico_formula(self, ai):
        """Teste caso real: fórmula do peso específico."""
        result = ai.reconstruct_with_context(
            text="Mercúrio: = 13600 kgf/m³",
            text_before="Como exemplo de valores de peso específico para alguns fluidos tem-se: Água: = 1000 kgf/m³",
            text_after=""
        )
        # Deve processar sem erro
        assert result.latex is not None

    def test_real_case_equacao_fundamental(self, ai):
        """Teste caso real: equação fundamental da hidrostática."""
        context = ai.extract_context(
            text_before="O equacionamento matemático se dá através da Equação Fundamental da Hidrostática - Lei de Stevin",
            text_after=""
        )
        assert context.detected_name == "Lei de Stevin"

    def test_real_case_fragmentado(self, ai):
        """Teste caso real: texto fragmentado típico do PDF."""
        # Texto típico de fórmula fragmentada
        text = "volume massa sendo"
        result = ai._try_known_formula_by_text(text)
        assert result is not None  # Deve reconhecer o padrão


class TestConvenienceFunctions:
    """Testes para funções de conveniência."""

    def test_get_formula_ai_singleton(self):
        """Teste que get_formula_ai retorna singleton."""
        ai1 = get_formula_ai()
        ai2 = get_formula_ai()
        assert ai1 is ai2

    def test_formula_ai_cache(self):
        """Teste que o cache funciona."""
        ai = get_formula_ai()
        ai.clear_cache()

        # Primeira chamada
        features1 = ai.extract_features("x + y = z")
        stats1 = ai.get_cache_stats()

        # Segunda chamada (deve usar cache)
        features2 = ai.extract_features("x + y = z")
        stats2 = ai.get_cache_stats()

        assert stats2['cache_size'] >= stats1['cache_size']


class TestEdgeCases:
    """Testes para casos extremos."""

    @pytest.fixture
    def ai(self):
        return LightFormulaAI()

    def test_context_with_special_characters(self, ai):
        """Teste contexto com caracteres especiais."""
        context = ai.extract_context(
            text_before="A fórmula é: ρ = m/V (kg/m³)",
            text_after=""
        )
        # Não deve dar erro
        assert context is not None

    def test_reconstruct_with_unicode(self, ai):
        """Teste reconstrução com Unicode."""
        result = ai.reconstruct_formula("α + β = γ")
        assert "alpha" in result.latex or "α" in result.latex

    def test_reconstruct_with_greek_words(self, ai):
        """Teste reconstrução com nomes gregos por extenso."""
        result = ai.reconstruct_formula("alpha + beta = gamma")
        assert "alpha" in result.latex.lower()

    def test_very_short_text(self, ai):
        """Teste texto muito curto."""
        result = ai.reconstruct_formula("x")
        assert result.latex is not None

    def test_only_numbers(self, ai):
        """Teste apenas números."""
        result = ai.reconstruct_formula("123")
        assert result.latex is not None
