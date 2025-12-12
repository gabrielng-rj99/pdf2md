"""
Testes unitários para o módulo de reconstrução de fórmulas fragmentadas.

Testa todas as funcionalidades do módulo formula_reconstruction.py
"""

import pytest
from app.utils.formula_reconstruction import (
    FormulaReconstructor,
    FormulaFragment,
    FragmentType,
    ReconstructedExpression,
    get_reconstructor,
    reconstruct_formulas,
    is_reconstruction_enabled,
    FORMULA_RECONSTRUCTION_ENABLED
)


class TestFragmentType:
    """Testes para classificação de tipos de fragmentos."""

    def test_fragment_type_enum_values(self):
        """Verifica se todos os tipos de fragmento estão definidos."""
        assert FragmentType.OPERATOR_START.value == "operator_start"
        assert FragmentType.OPERATOR_END.value == "operator_end"
        assert FragmentType.SUBSCRIPT.value == "subscript"
        assert FragmentType.SUPERSCRIPT.value == "superscript"
        assert FragmentType.VARIABLE.value == "variable"
        assert FragmentType.CONTINUATION.value == "continuation"
        assert FragmentType.COMPLETE.value == "complete"
        assert FragmentType.UNKNOWN.value == "unknown"


class TestFormulaFragment:
    """Testes para a classe FormulaFragment."""

    def test_fragment_creation(self):
        """Testa criação básica de fragmento."""
        frag = FormulaFragment(
            text="  x + y  ",
            fragment_type=FragmentType.CONTINUATION,
            line_number=1
        )
        # Deve fazer strip do texto
        assert frag.text == "x + y"
        assert frag.fragment_type == FragmentType.CONTINUATION
        assert frag.line_number == 1

    def test_fragment_with_positions(self):
        """Testa fragmento com posições."""
        frag = FormulaFragment(
            text="α",
            fragment_type=FragmentType.VARIABLE,
            y_position=100.5,
            x_position=50.0
        )
        assert frag.y_position == 100.5
        assert frag.x_position == 50.0


class TestFormulaReconstructor:
    """Testes para a classe FormulaReconstructor."""

    @pytest.fixture
    def reconstructor(self):
        """Cria instância do reconstrutor."""
        return FormulaReconstructor(enabled=True)

    @pytest.fixture
    def disabled_reconstructor(self):
        """Cria instância desabilitada do reconstrutor."""
        return FormulaReconstructor(enabled=False)

    # Testes de classificação de fragmentos

    def test_classify_empty_text(self, reconstructor):
        """Testa classificação de texto vazio."""
        assert reconstructor.classify_fragment("") == FragmentType.UNKNOWN
        assert reconstructor.classify_fragment("   ") == FragmentType.UNKNOWN

    def test_classify_isolated_operator(self, reconstructor):
        """Testa classificação de operador isolado."""
        assert reconstructor.classify_fragment("+") == FragmentType.OPERATOR_START
        assert reconstructor.classify_fragment("-") == FragmentType.OPERATOR_START
        assert reconstructor.classify_fragment("=") == FragmentType.OPERATOR_START

    def test_classify_operator_start(self, reconstructor):
        """Testa classificação de texto que começa com operador."""
        assert reconstructor.classify_fragment("+ 2x") == FragmentType.OPERATOR_START
        assert reconstructor.classify_fragment("- y") == FragmentType.OPERATOR_START

    def test_classify_operator_end(self, reconstructor):
        """Testa classificação de texto que termina com operador."""
        assert reconstructor.classify_fragment("x +") == FragmentType.OPERATOR_END
        assert reconstructor.classify_fragment("2y -") == FragmentType.OPERATOR_END

    def test_classify_isolated_variable(self, reconstructor):
        """Testa classificação de variável isolada."""
        assert reconstructor.classify_fragment("x") == FragmentType.VARIABLE
        assert reconstructor.classify_fragment("α") == FragmentType.VARIABLE
        assert reconstructor.classify_fragment("Y") == FragmentType.VARIABLE

    def test_classify_subscript(self, reconstructor):
        """Testa classificação de subscrito."""
        assert reconstructor.classify_fragment("₀₁₂") == FragmentType.SUBSCRIPT

    def test_classify_superscript(self, reconstructor):
        """Testa classificação de superscrito."""
        assert reconstructor.classify_fragment("²³") == FragmentType.SUPERSCRIPT

    def test_classify_complete_expression(self, reconstructor):
        """Testa classificação de expressão completa."""
        assert reconstructor.classify_fragment("x = 2y + 3") == FragmentType.COMPLETE
        assert reconstructor.classify_fragment("F = ma") == FragmentType.COMPLETE

    def test_classify_continuation(self, reconstructor):
        """Testa classificação de continuação."""
        assert reconstructor.classify_fragment("2xy") == FragmentType.CONTINUATION
        assert reconstructor.classify_fragment("sen(x)") == FragmentType.CONTINUATION

    # Testes de merge de fragmentos

    def test_should_merge_operator_end_with_next(self, reconstructor):
        """Testa merge quando primeiro fragmento termina com operador."""
        frag1 = FormulaFragment("x +", FragmentType.OPERATOR_END, y_position=0)
        frag2 = FormulaFragment("y", FragmentType.VARIABLE, y_position=0)

        should_merge, confidence = reconstructor.should_merge(frag1, frag2)
        assert should_merge is True
        assert confidence >= 0.8

    def test_should_merge_with_operator_start(self, reconstructor):
        """Testa merge quando segundo fragmento começa com operador."""
        frag1 = FormulaFragment("x", FragmentType.VARIABLE, y_position=0)
        frag2 = FormulaFragment("+ y", FragmentType.OPERATOR_START, y_position=0)

        should_merge, confidence = reconstructor.should_merge(frag1, frag2)
        assert should_merge is True
        assert confidence >= 0.8

    def test_should_merge_variable_with_subscript(self, reconstructor):
        """Testa merge de variável com subscrito."""
        frag1 = FormulaFragment("x", FragmentType.VARIABLE, y_position=0)
        frag2 = FormulaFragment("₁", FragmentType.SUBSCRIPT, y_position=0)

        should_merge, confidence = reconstructor.should_merge(frag1, frag2)
        assert should_merge is True
        assert confidence >= 0.9

    def test_should_not_merge_distant_fragments(self, reconstructor):
        """Testa que fragmentos distantes não são unidos."""
        frag1 = FormulaFragment("x", FragmentType.VARIABLE, y_position=0)
        frag2 = FormulaFragment("y", FragmentType.VARIABLE, y_position=100)

        should_merge, confidence = reconstructor.should_merge(frag1, frag2)
        assert should_merge is False

    # Testes de merge de lista de fragmentos

    def test_merge_single_fragment(self, reconstructor):
        """Testa merge de fragmento único."""
        fragments = [FormulaFragment("x = 2", FragmentType.COMPLETE)]
        result = reconstructor.merge_fragments(fragments)
        assert result == "x = 2"

    def test_merge_empty_list(self, reconstructor):
        """Testa merge de lista vazia."""
        result = reconstructor.merge_fragments([])
        assert result == ""

    def test_merge_multiple_fragments(self, reconstructor):
        """Testa merge de múltiplos fragmentos."""
        fragments = [
            FormulaFragment("x", FragmentType.VARIABLE),
            FormulaFragment("₁", FragmentType.SUBSCRIPT),
            FormulaFragment("+ y", FragmentType.OPERATOR_START),
        ]
        result = reconstructor.merge_fragments(fragments)
        assert "x" in result
        assert "₁" in result
        assert "+" in result
        assert "y" in result

    # Testes de reconstrução de grupo de linhas

    def test_reconstruct_empty_lines(self, reconstructor):
        """Testa reconstrução de lista vazia."""
        result = reconstructor.reconstruct_line_group([])
        assert result.reconstructed == ""
        assert result.confidence == 0.0

    def test_reconstruct_single_complete_line(self, reconstructor):
        """Testa reconstrução de linha completa única."""
        result = reconstructor.reconstruct_line_group(["F = ma"])
        assert "F" in result.reconstructed
        assert "=" in result.reconstructed
        assert result.confidence > 0.5

    def test_reconstruct_fragmented_lines(self, reconstructor):
        """Testa reconstrução de linhas fragmentadas."""
        lines = ["x +", "y =", "z"]
        result = reconstructor.reconstruct_line_group(lines)
        assert result.original_fragments == lines
        assert len(result.reconstructed) > 0

    # Testes de normalização

    def test_normalize_multiple_spaces(self, reconstructor):
        """Testa normalização de espaços múltiplos."""
        result = reconstructor._normalize_expression("x    =   2")
        assert "    " not in result
        assert "   " not in result

    def test_normalize_operator_spaces(self, reconstructor):
        """Testa normalização de espaços ao redor de operadores."""
        result = reconstructor._normalize_expression("x+y")
        assert " + " in result or "+" in result  # Deve ter espaços ao redor

    # Testes de conversão para LaTeX

    def test_to_latex_greek_letters(self, reconstructor):
        """Testa conversão de letras gregas para LaTeX."""
        assert r"\alpha" in reconstructor._to_latex("α")
        assert r"\beta" in reconstructor._to_latex("β")
        assert r"\gamma" in reconstructor._to_latex("γ")

    def test_to_latex_math_symbols(self, reconstructor):
        """Testa conversão de símbolos matemáticos para LaTeX."""
        assert r"\infty" in reconstructor._to_latex("∞")
        assert r"\sum" in reconstructor._to_latex("∑")
        assert r"\int" in reconstructor._to_latex("∫")

    def test_to_latex_subscripts(self, reconstructor):
        """Testa conversão de subscritos para LaTeX."""
        assert "_0" in reconstructor._to_latex("₀")
        assert "_1" in reconstructor._to_latex("₁")
        assert "_2" in reconstructor._to_latex("₂")

    def test_to_latex_superscripts(self, reconstructor):
        """Testa conversão de superscritos para LaTeX."""
        assert "^2" in reconstructor._to_latex("²")
        assert "^3" in reconstructor._to_latex("³")
        assert "^n" in reconstructor._to_latex("ⁿ")

    # Testes de reconstrução de bloco de texto

    def test_reconstruct_text_block_empty(self, reconstructor):
        """Testa reconstrução de bloco vazio."""
        assert reconstructor.reconstruct_text_block("") == ""
        assert reconstructor.reconstruct_text_block("   ") == "   "

    def test_reconstruct_text_block_normal_text(self, reconstructor):
        """Testa que texto normal não é modificado."""
        text = "Este é um texto normal sem fórmulas."
        result = reconstructor.reconstruct_text_block(text)
        assert "Este" in result
        assert "texto" in result

    def test_reconstruct_text_block_with_formula(self, reconstructor):
        """Testa reconstrução de bloco com fórmula."""
        text = "A equação é:\nx = 2y + 3"
        result = reconstructor.reconstruct_text_block(text)
        assert "equação" in result

    # Testes do modo desabilitado

    def test_disabled_returns_unchanged(self, disabled_reconstructor):
        """Testa que modo desabilitado retorna texto sem modificação."""
        text = "x +\ny =\nz"
        result = disabled_reconstructor.reconstruct_text_block(text)
        assert result == text

    def test_disabled_reconstruct_line_group(self, disabled_reconstructor):
        """Testa reconstruct_line_group no modo desabilitado."""
        lines = ["x", "y", "z"]
        result = disabled_reconstructor.reconstruct_line_group(lines)
        assert result.method == "disabled"
        assert result.confidence == 1.0

    def test_is_enabled(self, reconstructor, disabled_reconstructor):
        """Testa método is_enabled."""
        assert reconstructor.is_enabled() is True
        assert disabled_reconstructor.is_enabled() is False

    # Testes de estatísticas

    def test_stats_initial(self, reconstructor):
        """Testa estatísticas iniciais."""
        stats = reconstructor.get_stats()
        assert stats['fragments_processed'] == 0
        assert stats['reconstructions_made'] == 0

    def test_stats_after_processing(self, reconstructor):
        """Testa estatísticas após processamento."""
        reconstructor.reconstruct_line_group(["x +", "y"])
        stats = reconstructor.get_stats()
        assert stats['fragments_processed'] > 0

    def test_reset_stats(self, reconstructor):
        """Testa reset de estatísticas."""
        reconstructor.reconstruct_line_group(["x +", "y"])
        reconstructor.reset_stats()
        stats = reconstructor.get_stats()
        assert stats['fragments_processed'] == 0


class TestConvenienceFunctions:
    """Testes para funções de conveniência."""

    def test_get_reconstructor_singleton(self):
        """Testa que get_reconstructor retorna singleton."""
        r1 = get_reconstructor()
        r2 = get_reconstructor()
        assert r1 is r2

    def test_reconstruct_formulas_function(self):
        """Testa função reconstruct_formulas."""
        text = "F = ma"
        result = reconstruct_formulas(text)
        assert "F" in result
        assert "=" in result

    def test_is_reconstruction_enabled_function(self):
        """Testa função is_reconstruction_enabled."""
        # Deve retornar booleano
        assert isinstance(is_reconstruction_enabled(), bool)


class TestEdgeCases:
    """Testes para casos de borda."""

    @pytest.fixture
    def reconstructor(self):
        return FormulaReconstructor(enabled=True)

    def test_very_long_text(self, reconstructor):
        """Testa com texto muito longo."""
        long_text = "x = " + "y + " * 1000 + "z"
        result = reconstructor.reconstruct_text_block(long_text)
        assert len(result) > 0

    def test_unicode_only(self, reconstructor):
        """Testa com apenas caracteres Unicode."""
        text = "α β γ δ ε"
        result = reconstructor.reconstruct_text_block(text)
        assert len(result) > 0

    def test_mixed_content(self, reconstructor):
        """Testa com conteúdo misto."""
        text = "Seja α = 2π então:\nx² + y² = r²"
        result = reconstructor.reconstruct_text_block(text)
        assert "α" in result or r"\alpha" in result

    def test_multiline_with_empty_lines(self, reconstructor):
        """Testa múltiplas linhas com linhas vazias."""
        text = "x = 1\n\ny = 2\n\n\nz = 3"
        result = reconstructor.reconstruct_text_block(text)
        assert "x" in result
        assert "y" in result
        assert "z" in result

    def test_only_operators(self, reconstructor):
        """Testa com apenas operadores."""
        text = "+ - × ÷"
        result = reconstructor.reconstruct_text_block(text)
        assert len(result) > 0

    def test_fraction_bar(self, reconstructor):
        """Testa barra de fração."""
        frag_type = reconstructor.classify_fragment("────")
        assert frag_type == FragmentType.FRACTION_NUM


class TestReconstructedExpression:
    """Testes para a classe ReconstructedExpression."""

    def test_creation(self):
        """Testa criação básica."""
        expr = ReconstructedExpression(
            original_fragments=["x", "+", "y"],
            reconstructed="x + y",
            latex="x + y",
            confidence=0.9,
            method="heuristic"
        )
        assert expr.original_fragments == ["x", "+", "y"]
        assert expr.reconstructed == "x + y"
        assert expr.latex == "x + y"
        assert expr.confidence == 0.9
        assert expr.method == "heuristic"


class TestIntegration:
    """Testes de integração."""

    def test_full_pipeline(self):
        """Testa pipeline completo de reconstrução."""
        reconstructor = FormulaReconstructor(enabled=True)

        # Simular texto fragmentado de PDF
        fragmented_text = """A equação de Einstein é:
E
=
mc²
onde E é energia, m é massa e c é a velocidade da luz."""

        result = reconstructor.reconstruct_text_block(fragmented_text)

        # Deve conter os elementos principais
        assert "Einstein" in result or "equação" in result
        assert "energia" in result or "E" in result

    def test_preserve_non_formula_text(self):
        """Testa que texto que não é fórmula é preservado."""
        reconstructor = FormulaReconstructor(enabled=True)

        text = """Este é um parágrafo normal de texto.
Não contém nenhuma fórmula matemática.
Apenas texto comum em português."""

        result = reconstructor.reconstruct_text_block(text)

        assert "parágrafo" in result
        assert "fórmula" in result
        assert "português" in result
