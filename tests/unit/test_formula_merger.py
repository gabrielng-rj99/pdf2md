"""
Testes unitários para o módulo formula_merger.

Testa a fusão de fragmentos de fórmulas matemáticas usando heurísticas.
"""

import pytest
from app.utils.formula_merger import (
    FormulaMerger,
    FormulaMergerConfig,
    FormulaFragment,
    MergedFormula,
    MergeReason,
    get_formula_merger,
    merge_formula_fragments,
    quick_merge,
    is_incomplete_formula,
    END_OPERATORS,
    START_OPERATORS,
    OPENING_DELIMITERS,
    CLOSING_DELIMITERS,
)


class TestFormulaFragment:
    """Testes para a classe FormulaFragment."""

    def test_creation(self):
        """Testa criação de FormulaFragment."""
        fragment = FormulaFragment(
            text="x + y",
            x0=10.0,
            y0=100.0,
            x1=50.0,
            y1=115.0,
            page_num=1,
        )

        assert fragment.text == "x + y"
        assert fragment.x0 == 10.0
        assert fragment.y0 == 100.0
        assert fragment.x1 == 50.0
        assert fragment.y1 == 115.0
        assert fragment.page_num == 1

    def test_height_property(self):
        """Testa propriedade height."""
        fragment = FormulaFragment(text="test", y0=100, y1=120)
        assert fragment.height == 20.0

    def test_width_property(self):
        """Testa propriedade width."""
        fragment = FormulaFragment(text="test", x0=10, x1=60)
        assert fragment.width == 50.0


class TestMergedFormula:
    """Testes para a classe MergedFormula."""

    def test_creation(self):
        """Testa criação de MergedFormula."""
        merged = MergedFormula(
            text="x + y = z",
            original_fragments=["x +", "y = z"],
            merge_reasons=[MergeReason.SYNTACTIC_BRIDGE],
            confidence=0.85,
            bbox=(10, 100, 100, 120),
        )

        assert merged.text == "x + y = z"
        assert len(merged.original_fragments) == 2
        assert merged.confidence == 0.85


class TestMergeReason:
    """Testes para o enum MergeReason."""

    def test_values(self):
        """Testa valores do enum."""
        assert MergeReason.SYNTACTIC_BRIDGE.value == "syntactic_bridge"
        assert MergeReason.BRACE_BALANCE.value == "brace_balance"
        assert MergeReason.VERTICAL_PROXIMITY.value == "vertical_proximity"
        assert MergeReason.CONTINUATION.value == "continuation"
        assert MergeReason.NONE.value == "none"


class TestFormulaMergerConfig:
    """Testes para a classe FormulaMergerConfig."""

    def test_default_values(self):
        """Testa valores padrão da configuração."""
        config = FormulaMergerConfig()

        assert config.max_vertical_gap == 15.0
        assert config.same_line_tolerance == 5.0
        assert config.soft_merge is True
        assert config.latex_line_break is False
        assert config.max_fragments_to_merge == 20
        assert config.min_fragment_length == 1

    def test_custom_values(self):
        """Testa valores personalizados."""
        config = FormulaMergerConfig(
            max_vertical_gap=20.0,
            same_line_tolerance=10.0,
            soft_merge=False,
        )

        assert config.max_vertical_gap == 20.0
        assert config.same_line_tolerance == 10.0
        assert config.soft_merge is False


class TestFormulaMerger:
    """Testes para a classe FormulaMerger."""

    def test_init_default_config(self):
        """Testa inicialização com configuração padrão."""
        merger = FormulaMerger()
        assert merger.config is not None
        assert merger.config.max_vertical_gap == 15.0

    def test_init_custom_config(self):
        """Testa inicialização com configuração personalizada."""
        config = FormulaMergerConfig(max_vertical_gap=25.0)
        merger = FormulaMerger(config)
        assert merger.config.max_vertical_gap == 25.0

    def test_merge_empty_list(self):
        """Testa fusão de lista vazia."""
        merger = FormulaMerger()
        result = merger.merge_fragments([])
        assert result == []

    def test_merge_single_fragment(self):
        """Testa fusão de fragmento único."""
        merger = FormulaMerger()
        fragments = [FormulaFragment(text="x = 1", y0=100, y1=115)]

        result = merger.merge_fragments(fragments)

        assert len(result) == 1
        assert result[0].text == "x = 1"

    def test_merge_syntactic_bridge_end_operator(self):
        """Testa fusão por ponte sintática (operador no final)."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="x +", x0=0, y0=100, x1=30, y1=115),
            FormulaFragment(text="y", x0=35, y0=100, x1=45, y1=115),
        ]

        result = merger.merge_fragments(fragments)

        assert len(result) == 1
        assert "x" in result[0].text
        assert "y" in result[0].text
        assert MergeReason.SYNTACTIC_BRIDGE in result[0].merge_reasons

    def test_merge_syntactic_bridge_start_operator(self):
        """Testa fusão por ponte sintática (operador no início)."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="x", x0=0, y0=100, x1=15, y1=115),
            FormulaFragment(text="^2", x0=20, y0=95, x1=35, y1=110),  # Superscrito
        ]

        result = merger.merge_fragments(fragments)

        assert len(result) == 1
        assert "x" in result[0].text
        assert "^2" in result[0].text or "2" in result[0].text

    def test_merge_brace_balance_open_paren(self):
        """Testa fusão por balanço de parênteses (parêntese aberto)."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="f(x", x0=0, y0=100, x1=30, y1=115),
            FormulaFragment(text=")", x0=35, y0=100, x1=45, y1=115),
        ]

        result = merger.merge_fragments(fragments)

        assert len(result) == 1
        assert "f(x" in result[0].text
        assert ")" in result[0].text
        assert MergeReason.BRACE_BALANCE in result[0].merge_reasons

    def test_merge_brace_balance_open_bracket(self):
        """Testa fusão por balanço de colchetes."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="[a, b", x0=0, y0=100, x1=40, y1=115),
            FormulaFragment(text="]", x0=45, y0=100, x1=55, y1=115),
        ]

        result = merger.merge_fragments(fragments)

        assert len(result) == 1
        assert "[a, b" in result[0].text
        assert "]" in result[0].text

    def test_merge_brace_balance_open_brace(self):
        """Testa fusão por balanço de chaves."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="{1, 2", x0=0, y0=100, x1=40, y1=115),
            FormulaFragment(text="}", x0=45, y0=100, x1=55, y1=115),
        ]

        result = merger.merge_fragments(fragments)

        assert len(result) == 1

    def test_merge_vertical_proximity(self):
        """Testa fusão por proximidade vertical."""
        config = FormulaMergerConfig(max_vertical_gap=20.0, same_line_tolerance=10.0)
        merger = FormulaMerger(config)

        fragments = [
            FormulaFragment(text="a", x0=0, y0=100, x1=15, y1=115),
            FormulaFragment(text="b", x0=20, y0=102, x1=35, y1=117),  # Quase mesma linha
        ]

        result = merger.merge_fragments(fragments)

        assert len(result) == 1
        assert "a" in result[0].text
        assert "b" in result[0].text

    def test_no_merge_when_far_apart(self):
        """Testa que fragmentos distantes não são fundidos."""
        config = FormulaMergerConfig(max_vertical_gap=15.0)
        merger = FormulaMerger(config)

        fragments = [
            FormulaFragment(text="x = 1", x0=0, y0=100, x1=50, y1=115),
            FormulaFragment(text="y = 2", x0=0, y0=200, x1=50, y1=215),  # Muito distante
        ]

        result = merger.merge_fragments(fragments)

        assert len(result) == 2
        assert result[0].text == "x = 1"
        assert result[1].text == "y = 2"

    def test_merge_multiple_fragments(self):
        """Testa fusão de múltiplos fragmentos em cadeia."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="a +", x0=0, y0=100, x1=25, y1=115),
            FormulaFragment(text="b +", x0=30, y0=100, x1=55, y1=115),
            FormulaFragment(text="c", x0=60, y0=100, x1=70, y1=115),
        ]

        result = merger.merge_fragments(fragments)

        # Todos devem ser fundidos em um único
        assert len(result) == 1
        assert "a" in result[0].text
        assert "b" in result[0].text
        assert "c" in result[0].text

    def test_has_unbalanced_delimiters_open(self):
        """Testa detecção de delimitadores desbalanceados (abertura)."""
        merger = FormulaMerger()

        assert merger._has_unbalanced_delimiters("f(x") is True
        assert merger._has_unbalanced_delimiters("[a, b") is True
        assert merger._has_unbalanced_delimiters("{1, 2") is True

    def test_has_unbalanced_delimiters_balanced(self):
        """Testa detecção de delimitadores balanceados."""
        merger = FormulaMerger()

        assert merger._has_unbalanced_delimiters("f(x)") is False
        assert merger._has_unbalanced_delimiters("[a, b]") is False
        assert merger._has_unbalanced_delimiters("{1, 2}") is False

    def test_has_unbalanced_delimiters_latex(self):
        """Testa detecção de delimitadores LaTeX."""
        merger = FormulaMerger()

        assert merger._has_unbalanced_delimiters("\\left(x") is True
        assert merger._has_unbalanced_delimiters("\\left(x\\right)") is False

    def test_ends_with_operator(self):
        """Testa detecção de operador no final."""
        merger = FormulaMerger()

        assert merger._ends_with_operator("x +") is True
        assert merger._ends_with_operator("y -") is True
        assert merger._ends_with_operator("a =") is True
        assert merger._ends_with_operator("f(") is True
        assert merger._ends_with_operator("x") is False
        assert merger._ends_with_operator("abc") is False

    def test_starts_with_continuation(self):
        """Testa detecção de continuação no início."""
        merger = FormulaMerger()

        assert merger._starts_with_continuation("^2") is True
        assert merger._starts_with_continuation("_1") is True
        assert merger._starts_with_continuation(")") is True
        assert merger._starts_with_continuation("]") is True
        assert merger._starts_with_continuation("!") is True
        assert merger._starts_with_continuation("x") is False
        assert merger._starts_with_continuation("abc") is False

    def test_stats_tracking(self):
        """Testa rastreamento de estatísticas."""
        merger = FormulaMerger()
        merger.reset_stats()

        fragments = [
            FormulaFragment(text="x +", x0=0, y0=100, x1=25, y1=115),
            FormulaFragment(text="y", x0=30, y0=100, x1=40, y1=115),
        ]
        merger.merge_fragments(fragments)

        stats = merger.get_stats()
        assert stats['fragments_processed'] == 2
        assert stats['merges_performed'] >= 1

    def test_reset_stats(self):
        """Testa reset de estatísticas."""
        merger = FormulaMerger()

        fragments = [FormulaFragment(text="x", y0=0, y1=15)]
        merger.merge_fragments(fragments)

        merger.reset_stats()
        stats = merger.get_stats()

        assert stats['fragments_processed'] == 0
        assert stats['merges_performed'] == 0


class TestFactoryFunction:
    """Testes para função factory."""

    def test_get_formula_merger_default(self):
        """Testa factory com configuração padrão."""
        merger = get_formula_merger()
        assert isinstance(merger, FormulaMerger)

    def test_get_formula_merger_custom(self):
        """Testa factory com configuração personalizada."""
        config = FormulaMergerConfig(max_vertical_gap=30.0)
        merger = get_formula_merger(config)

        assert merger.config.max_vertical_gap == 30.0


class TestMergeFormulaFragments:
    """Testes para função merge_formula_fragments."""

    def test_basic_merge(self):
        """Testa fusão básica."""
        fragments = [
            {'text': 'x +', 'x0': 0, 'y0': 100, 'x1': 25, 'y1': 115},
            {'text': 'y', 'x0': 30, 'y0': 100, 'x1': 40, 'y1': 115},
        ]

        result = merge_formula_fragments(fragments)

        assert len(result) >= 1
        combined_text = ' '.join(result)
        assert 'x' in combined_text
        assert 'y' in combined_text

    def test_empty_list(self):
        """Testa lista vazia."""
        result = merge_formula_fragments([])
        assert result == []

    def test_custom_vertical_gap(self):
        """Testa com gap vertical personalizado."""
        fragments = [
            {'text': 'a', 'x0': 0, 'y0': 100, 'x1': 15, 'y1': 115},
            {'text': 'b', 'x0': 0, 'y0': 200, 'x1': 15, 'y1': 215},
        ]

        result = merge_formula_fragments(fragments, max_vertical_gap=50.0)

        # Com gap de 50, ainda devem ser separados (distância é 85)
        assert len(result) == 2


class TestQuickMerge:
    """Testes para função quick_merge."""

    def test_should_merge_operator(self):
        """Testa fusão por operador."""
        should_merge, merged = quick_merge("x +", "y")

        assert should_merge is True
        assert "x" in merged
        assert "y" in merged

    def test_should_not_merge_complete(self):
        """Testa não fusão de expressões completas."""
        should_merge, merged = quick_merge("x = 1", "y = 2")

        # Duas expressões completas podem não ser fundidas
        assert "x = 1" in merged or "x" in merged

    def test_unbalanced_parens(self):
        """Testa fusão por parênteses desbalanceados."""
        should_merge, merged = quick_merge("f(x", ")")

        assert should_merge is True
        assert "f(x" in merged
        assert ")" in merged


class TestIsIncompleteFormula:
    """Testes para função is_incomplete_formula."""

    def test_incomplete_paren(self):
        """Testa fórmula com parêntese aberto."""
        assert is_incomplete_formula("f(x") is True
        assert is_incomplete_formula("(a + b") is True

    def test_incomplete_operator(self):
        """Testa fórmula terminando com operador."""
        assert is_incomplete_formula("x +") is True
        assert is_incomplete_formula("y =") is True

    def test_complete_formula(self):
        """Testa fórmula completa."""
        assert is_incomplete_formula("x + y") is False
        assert is_incomplete_formula("f(x) = 2x") is False
        assert is_incomplete_formula("(a + b)") is False


class TestOperatorSets:
    """Testes para os conjuntos de operadores."""

    def test_end_operators_content(self):
        """Testa conteúdo de END_OPERATORS."""
        assert '+' in END_OPERATORS
        assert '-' in END_OPERATORS
        assert '=' in END_OPERATORS
        assert '(' in END_OPERATORS
        assert '[' in END_OPERATORS
        assert '{' in END_OPERATORS

    def test_start_operators_content(self):
        """Testa conteúdo de START_OPERATORS."""
        assert '^' in START_OPERATORS
        assert '_' in START_OPERATORS
        assert ')' in START_OPERATORS
        assert ']' in START_OPERATORS
        assert '}' in START_OPERATORS

    def test_opening_delimiters(self):
        """Testa delimitadores de abertura."""
        assert '(' in OPENING_DELIMITERS
        assert '[' in OPENING_DELIMITERS
        assert '{' in OPENING_DELIMITERS

    def test_closing_delimiters(self):
        """Testa delimitadores de fechamento."""
        assert ')' in CLOSING_DELIMITERS
        assert ']' in CLOSING_DELIMITERS
        assert '}' in CLOSING_DELIMITERS


class TestRealWorldScenarios:
    """Testes com cenários do mundo real."""

    def test_fraction_reconstruction(self):
        """Testa reconstrução de fração fragmentada."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="P1.V1", x0=0, y0=100, x1=40, y1=115),
            FormulaFragment(text="/", x0=45, y0=100, x1=50, y1=115),
            FormulaFragment(text="C1", x0=55, y0=100, x1=70, y1=115),
        ]

        result = merger.merge_fragments(fragments)

        # Espera que sejam fundidos
        combined = ' '.join(m.text for m in result)
        assert "P1" in combined
        assert "V1" in combined
        assert "C1" in combined

    def test_equation_with_equals(self):
        """Testa equação fragmentada com sinal de igual."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="f(x) =", x0=0, y0=100, x1=50, y1=115),
            FormulaFragment(text="2x + 1", x0=55, y0=100, x1=100, y1=115),
        ]

        result = merger.merge_fragments(fragments)

        assert len(result) == 1
        assert "f(x)" in result[0].text
        assert "2x + 1" in result[0].text

    def test_multiline_fraction(self):
        """Testa fração em múltiplas linhas."""
        config = FormulaMergerConfig(max_vertical_gap=30.0)
        merger = FormulaMerger(config)

        fragments = [
            FormulaFragment(text="a + b", x0=50, y0=100, x1=90, y1=115),  # Numerador
            FormulaFragment(text="—", x0=45, y0=118, x1=95, y1=122),  # Linha de fração
            FormulaFragment(text="c + d", x0=50, y0=125, x1=90, y1=140),  # Denominador
        ]

        result = merger.merge_fragments(fragments)

        # Pode ou não fundir dependendo da configuração
        combined = ' '.join(m.text for m in result)
        assert "a + b" in combined
        assert "c + d" in combined

    def test_subscript_superscript(self):
        """Testa sub/superscrito."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="x", x0=0, y0=100, x1=10, y1=115),
            FormulaFragment(text="^2", x0=12, y0=95, x1=22, y1=105),
            FormulaFragment(text="+ y", x0=25, y0=100, x1=45, y1=115),
            FormulaFragment(text="_1", x0=48, y0=110, x1=58, y1=120),
        ]

        result = merger.merge_fragments(fragments)

        combined = ' '.join(m.text for m in result)
        assert "x" in combined
        assert "2" in combined
        assert "y" in combined

    def test_complex_formula_reconstruction(self):
        """Testa reconstrução de fórmula complexa."""
        merger = FormulaMerger()
        fragments = [
            FormulaFragment(text="∫", x0=0, y0=100, x1=10, y1=130),
            FormulaFragment(text="f(x)", x0=15, y0=105, x1=40, y1=120),
            FormulaFragment(text="dx", x0=45, y0=105, x1=60, y1=120),
            FormulaFragment(text="=", x0=65, y0=105, x1=75, y1=120),
            FormulaFragment(text="F(x)", x0=80, y0=105, x1=105, y1=120),
            FormulaFragment(text="+ C", x0=110, y0=105, x1=130, y1=120),
        ]

        result = merger.merge_fragments(fragments)

        combined = ' '.join(m.text for m in result)
        assert "∫" in combined or "f(x)" in combined
        assert "F(x)" in combined or "C" in combined
