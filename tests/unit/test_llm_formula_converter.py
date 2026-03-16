"""
Testes unitários para o módulo LLM Formula Converter.
"""

import pytest
from app.utils.llm_formula_converter import (
    LLMConfig,
    LLMFormulaConverter,
    SimpleFallbackConverter,
    select_model_for_ram,
    get_formula_converter,
    check_llm_available,
    get_ram_limit,
    set_ram_limit,
    get_recommended_model,
    RAM_LIMIT_GB,
)


# =============================================================================
# LLMConfig Tests
# =============================================================================

class TestLLMConfig:
    """Testes para a configuração do LLM."""

    def test_default_config(self):
        """Teste de configuração padrão."""
        config = LLMConfig()
        assert config.ram_limit_gb == RAM_LIMIT_GB
        assert config.batch_size == 10
        assert config.use_cache is True
        assert config.fallback_to_original is True

    def test_custom_config(self):
        """Teste de configuração personalizada."""
        config = LLMConfig(
            ram_limit_gb=8.0,
            batch_size=20,
            use_cache=False,
        )
        assert config.ram_limit_gb == 8.0
        assert config.batch_size == 20
        assert config.use_cache is False


# =============================================================================
# Model Selection Tests
# =============================================================================

class TestModelSelection:
    """Testes para seleção de modelo baseada em RAM."""

    def test_select_model_1gb(self):
        """Seleciona modelo para 1GB RAM."""
        model_id, model_name = select_model_for_ram(1.0)
        assert "0.5B" in model_name or "Qwen" in model_id

    def test_select_model_4gb(self):
        """Seleciona modelo para 4GB RAM."""
        model_id, model_name = select_model_for_ram(4.0)
        assert "Qwen" in model_id

    def test_select_model_8gb(self):
        """Seleciona modelo para 8GB RAM."""
        model_id, model_name = select_model_for_ram(8.0)
        assert "Qwen" in model_id

    def test_select_model_12gb(self):
        """Seleciona modelo para 12GB RAM."""
        model_id, model_name = select_model_for_ram(12.0)
        assert "Qwen" in model_id

    def test_get_recommended_model(self):
        """Teste de get_recommended_model."""
        model_name = get_recommended_model(4.0)
        assert isinstance(model_name, str)
        assert len(model_name) > 0


# =============================================================================
# LLMFormulaConverter Tests
# =============================================================================

class TestLLMFormulaConverterInit:
    """Testes de inicialização do LLMFormulaConverter."""

    def test_init_default(self):
        """Teste de inicialização com config padrão."""
        converter = LLMFormulaConverter()
        assert converter.config is not None
        assert converter._loaded is False
        assert converter._model is None

    def test_init_custom_config(self):
        """Teste de inicialização com config personalizada."""
        config = LLMConfig(ram_limit_gb=8.0)
        converter = LLMFormulaConverter(config)
        assert converter.config.ram_limit_gb == 8.0

    def test_check_dependencies(self):
        """Teste de verificação de dependências."""
        converter = LLMFormulaConverter()
        # Deve retornar bool sem erro
        result = converter._check_dependencies()
        assert isinstance(result, bool)

    def test_is_available(self):
        """Teste de is_available."""
        converter = LLMFormulaConverter()
        result = converter.is_available()
        assert isinstance(result, bool)


class TestLLMFormulaConverterHeuristics:
    """Testes das heurísticas do conversor."""

    def test_has_potential_math_greek(self):
        """Detecta potencial matemático com letras gregas."""
        converter = LLMFormulaConverter()
        assert converter._has_potential_math("ρ = m/V") is True
        assert converter._has_potential_math("α + β = γ") is True

    def test_has_potential_math_equation(self):
        """Detecta potencial matemático com equações."""
        converter = LLMFormulaConverter()
        assert converter._has_potential_math("x = 5") is True
        assert converter._has_potential_math("y = mx + b") is True

    def test_has_potential_math_fraction(self):
        """Detecta potencial matemático com frações numéricas."""
        converter = LLMFormulaConverter()
        assert converter._has_potential_math("1/2") is True
        # Nota: "a/b" sozinho não é detectado pois pode ser texto normal
        # A heurística é conservadora para evitar falsos positivos
        assert converter._has_potential_math("x = a/b") is True  # Com equação

    def test_has_potential_math_superscript(self):
        """Detecta potencial matemático com superscritos."""
        converter = LLMFormulaConverter()
        assert converter._has_potential_math("x²") is True
        assert converter._has_potential_math("m³") is True

    def test_no_potential_math_normal_text(self):
        """Não detecta matemática em texto normal."""
        converter = LLMFormulaConverter()
        assert converter._has_potential_math("Este é um texto normal") is False
        assert converter._has_potential_math("Olá mundo") is False


class TestLLMFormulaConverterStats:
    """Testes para estatísticas do conversor."""

    def test_stats_initial(self):
        """Estatísticas iniciais são zero."""
        converter = LLMFormulaConverter()
        stats = converter.get_stats()
        assert stats['lines_processed'] == 0
        assert stats['lines_converted'] == 0
        assert stats['cache_hits'] == 0
        assert stats['errors'] == 0

    def test_reset_stats(self):
        """Reset de estatísticas funciona."""
        converter = LLMFormulaConverter()
        converter._stats['lines_processed'] = 100
        converter.reset_stats()
        stats = converter.get_stats()
        assert stats['lines_processed'] == 0

    def test_get_model_info(self):
        """Teste de get_model_info."""
        converter = LLMFormulaConverter()
        info = converter.get_model_info()
        assert 'model_id' in info
        assert 'model_name' in info
        assert 'ram_limit_gb' in info
        assert 'loaded' in info
        assert 'available' in info


# =============================================================================
# SimpleFallbackConverter Tests
# =============================================================================

class TestSimpleFallbackConverter:
    """Testes para o conversor fallback simples."""

    def test_init(self):
        """Teste de inicialização."""
        converter = SimpleFallbackConverter()
        assert converter._stats is not None

    def test_convert_superscript(self):
        """Converte superscritos."""
        converter = SimpleFallbackConverter()
        result = converter.convert_line("x² + y³")
        assert "^{2}" in result
        assert "^{3}" in result

    def test_convert_subscript(self):
        """Converte subscritos."""
        converter = SimpleFallbackConverter()
        result = converter.convert_line("H₂O e CO₂")
        assert "_{2}" in result

    def test_preserve_normal_text(self):
        """Preserva texto normal."""
        converter = SimpleFallbackConverter()
        text = "Este é um texto normal"
        result = converter.convert_line(text)
        assert result == text

    def test_empty_line(self):
        """Linha vazia retorna vazia."""
        converter = SimpleFallbackConverter()
        assert converter.convert_line("") == ""
        assert converter.convert_line("   ") == "   "

    def test_convert_text_multiline(self):
        """Converte texto com múltiplas linhas."""
        converter = SimpleFallbackConverter()
        text = "x² mais\ny³"
        result = converter.convert_text(text)
        assert "\n" in result
        assert "^{2}" in result
        assert "^{3}" in result

    def test_stats(self):
        """Testa estatísticas."""
        converter = SimpleFallbackConverter()
        converter.convert_line("x²")
        stats = converter.get_stats()
        assert stats['lines_processed'] >= 1


# =============================================================================
# Utility Functions Tests
# =============================================================================

class TestUtilityFunctions:
    """Testes para funções utilitárias."""

    def test_check_llm_available(self):
        """Teste de check_llm_available."""
        available, message = check_llm_available()
        assert isinstance(available, bool)
        assert isinstance(message, str)
        assert len(message) > 0

    def test_get_ram_limit(self):
        """Teste de get_ram_limit."""
        limit = get_ram_limit()
        assert isinstance(limit, float)
        assert limit > 0

    def test_set_ram_limit(self):
        """Teste de set_ram_limit."""
        original = get_ram_limit()
        set_ram_limit(16.0)
        assert get_ram_limit() == 16.0
        # Restaurar
        set_ram_limit(original)

    def test_get_formula_converter_fallback(self):
        """Teste de get_formula_converter com fallback."""
        converter = get_formula_converter(use_llm=False)
        assert isinstance(converter, SimpleFallbackConverter)

    def test_get_formula_converter_llm(self):
        """Teste de get_formula_converter tentando LLM."""
        converter = get_formula_converter(use_llm=True)
        # Pode retornar LLM ou Fallback dependendo das dependências
        assert converter is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestFallbackIntegration:
    """Testes de integração do fallback."""

    def test_full_document_conversion(self):
        """Converte documento completo."""
        converter = SimpleFallbackConverter()
        text = """Capítulo 1

A fórmula x² + y² = r² descreve um círculo.
A água é H₂O e o dióxido de carbono é CO₂.

Seção 1.1

Para velocidade v = at, temos:
- Aceleração a em m/s²
- Tempo t em segundos
"""
        result = converter.convert_text(text)

        # Verifica conversões
        assert "^{2}" in result  # Superscritos convertidos
        assert "_{2}" in result  # Subscritos convertidos
        assert "Capítulo 1" in result  # Texto preservado
        assert "Seção 1.1" in result  # Texto preservado

    def test_mixed_content(self):
        """Converte conteúdo misto."""
        converter = SimpleFallbackConverter()
        text = "Energia E = mc² onde c é a velocidade da luz"
        result = converter.convert_line(text)

        assert "^{2}" in result
        assert "Energia" in result
        assert "velocidade da luz" in result


class TestEdgeCases:
    """Testes de casos extremos."""

    def test_multiple_superscripts(self):
        """Múltiplos superscritos na mesma linha."""
        converter = SimpleFallbackConverter()
        result = converter.convert_line("a² b³ c⁴ d⁵")
        assert result.count("^{") == 4

    def test_mixed_sub_super(self):
        """Mistura de sub e superscritos."""
        converter = SimpleFallbackConverter()
        result = converter.convert_line("x₁² + x₂³")
        assert "_{1}" in result
        assert "_{2}" in result
        assert "^{2}" in result
        assert "^{3}" in result

    def test_unicode_preservation(self):
        """Preserva outros caracteres Unicode."""
        converter = SimpleFallbackConverter()
        text = "α β γ δ ε → ← ↔"
        result = converter.convert_line(text)
        # Letras gregas devem ser preservadas (não convertidas pelo fallback)
        assert "α" in result
        assert "β" in result
        assert "→" in result

    def test_very_long_line(self):
        """Linha muito longa."""
        converter = SimpleFallbackConverter()
        text = "x² " * 100
        result = converter.convert_line(text)
        assert "^{2}" in result
        assert len(result) > 0

    def test_special_characters(self):
        """Caracteres especiais."""
        converter = SimpleFallbackConverter()
        text = "f(x) = x² + 2x + 1; g(y) = y³ - 1"
        result = converter.convert_line(text)
        assert "f(x)" in result
        assert "g(y)" in result
        assert "^{2}" in result
        assert "^{3}" in result
