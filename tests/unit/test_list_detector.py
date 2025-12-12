"""
Testes unitários para o módulo de detecção de listas.

Testa a detecção e formatação de:
- Bullets Unicode e especiais (Wingdings, Symbol)
- Listas numeradas
- Listas com letras
- Listas com romanos
- Listas inline
- Continuação de itens fragmentados
"""

import pytest
from app.utils.list_detector import (
    ListDetector,
    ListType,
    ListItem,
    get_list_detector,
    is_list_item,
    format_list_item,
    process_paragraph_lists,
)


class TestListItem:
    """Testes para a classe ListItem."""

    def test_bullet_markdown(self):
        """Teste formatação de item bullet."""
        item = ListItem(text="Teste", list_type=ListType.BULLET, marker="-")
        assert item.markdown == "- Teste"

    def test_numbered_markdown(self):
        """Teste formatação de item numerado."""
        item = ListItem(text="Teste", list_type=ListType.NUMBERED, marker="1")
        assert item.markdown == "1. Teste"

    def test_lettered_markdown(self):
        """Teste formatação de item com letra."""
        item = ListItem(text="Teste", list_type=ListType.LETTERED, marker="a")
        assert item.markdown == "a) Teste"

    def test_roman_markdown(self):
        """Teste formatação de item romano."""
        item = ListItem(text="Teste", list_type=ListType.ROMAN, marker="ii")
        assert item.markdown == "ii. Teste"

    def test_checkbox_markdown(self):
        """Teste formatação de checkbox (deve ser bullet simples)."""
        item = ListItem(text="Teste", list_type=ListType.CHECKBOX, marker="☐")
        assert item.markdown == "- Teste"

    def test_indented_item(self):
        """Teste item com indentação."""
        item = ListItem(text="Sub-item", list_type=ListType.BULLET, marker="-", level=1)
        assert item.markdown == "  - Sub-item"

    def test_double_indented_item(self):
        """Teste item com indentação dupla."""
        item = ListItem(text="Sub-sub-item", list_type=ListType.BULLET, marker="-", level=2)
        assert item.markdown == "    - Sub-sub-item"


class TestListDetectorIsListItem:
    """Testes para detecção de itens de lista."""

    @pytest.fixture
    def detector(self):
        return ListDetector()

    # Testes para bullets padrão
    def test_bullet_unicode(self, detector):
        """Teste bullet Unicode padrão."""
        assert detector.is_list_item("• Item de lista")
        assert detector.is_list_item("◦ Sub-item")
        assert detector.is_list_item("■ Item quadrado")
        assert detector.is_list_item("○ Item círculo")

    def test_bullet_dash(self, detector):
        """Teste bullet com traço."""
        assert detector.is_list_item("- Item com traço")
        assert detector.is_list_item("– Item com en-dash")
        assert detector.is_list_item("— Item com em-dash")

    def test_bullet_asterisk(self, detector):
        """Teste bullet com asterisco."""
        assert detector.is_list_item("* Item com asterisco")

    # Testes para caracteres especiais de fontes
    def test_wingdings_checkbox(self, detector):
        """Teste checkbox Wingdings (\\uf0fc)."""
        assert detector.is_list_item("\uf0fc Item checkbox")
        assert detector.is_list_item("\uf0fc Ação de fluidos sobre superfícies")

    def test_symbol_bullet(self, detector):
        """Teste bullet Symbol (\\uf0b7)."""
        assert detector.is_list_item("\uf0b7 Item com symbol bullet")

    def test_checkbox_chars(self, detector):
        """Teste caracteres de checkbox."""
        assert detector.is_list_item("☐ Item não marcado")
        assert detector.is_list_item("☑ Item marcado")
        assert detector.is_list_item("✓ Item com check")
        assert detector.is_list_item("✗ Item com X")

    # Testes para listas numeradas
    def test_numbered_parenthesis(self, detector):
        """Teste lista numerada com parênteses."""
        assert detector.is_list_item("1) Primeiro item")
        assert detector.is_list_item("2) Segundo item")
        assert detector.is_list_item("10) Décimo item")

    def test_numbered_dash(self, detector):
        """Teste lista numerada com traço."""
        assert detector.is_list_item("1- Primeiro item")
        assert detector.is_list_item("2- Segundo item")

    def test_section_numbers_not_list(self, detector):
        """Teste que números de seção NÃO são lista."""
        assert not detector.is_list_item("1.1 – Mecânica dos Fluidos")
        assert not detector.is_list_item("1. 1 – Mecânica dos Fluidos")
        assert not detector.is_list_item("2.3.4 Subseção")
        assert not detector.is_list_item("1.2.3.4 – Título")

    # Testes para listas com letras
    def test_lettered_dot(self, detector):
        """Teste lista com letras e ponto."""
        assert detector.is_list_item("a. Primeiro item")
        assert detector.is_list_item("b. Segundo item")
        assert detector.is_list_item("A. Item maiúsculo")

    def test_lettered_parenthesis(self, detector):
        """Teste lista com letras e parênteses."""
        assert detector.is_list_item("a) Primeiro item")
        assert detector.is_list_item("b) Segundo item")

    # Testes para listas romanas
    def test_roman_lowercase(self, detector):
        """Teste lista romana minúscula."""
        assert detector.is_list_item("i. Primeiro")
        assert detector.is_list_item("ii. Segundo")
        assert detector.is_list_item("iii. Terceiro")
        assert detector.is_list_item("iv. Quarto")

    def test_roman_uppercase(self, detector):
        """Teste lista romana maiúscula."""
        assert detector.is_list_item("I. Primeiro")
        assert detector.is_list_item("II. Segundo")
        assert detector.is_list_item("III. Terceiro")

    # Testes negativos
    def test_not_list_regular_text(self, detector):
        """Teste que texto normal NÃO é lista."""
        assert not detector.is_list_item("Este é um texto normal.")
        assert not detector.is_list_item("A mecânica dos fluidos")
        assert not detector.is_list_item("O conceito de fluido")

    def test_not_list_empty(self, detector):
        """Teste texto vazio."""
        assert not detector.is_list_item("")
        assert not detector.is_list_item("   ")
        assert not detector.is_list_item("a")

    def test_not_list_heading(self, detector):
        """Teste que headings NÃO são lista."""
        assert not detector.is_list_item("CAPÍTULO 1 – Introdução")
        assert not detector.is_list_item("1.1 – Título da Seção")


class TestListDetectorDetectType:
    """Testes para detecção de tipo de lista."""

    @pytest.fixture
    def detector(self):
        return ListDetector()

    def test_detect_bullet(self, detector):
        """Teste detecção de bullet."""
        list_type, marker, content = detector.detect_list_type("• Item teste")
        assert list_type == ListType.BULLET
        assert content == "Item teste"

    def test_detect_checkbox(self, detector):
        """Teste detecção de checkbox."""
        list_type, marker, content = detector.detect_list_type("\uf0fc Item checkbox")
        assert list_type == ListType.CHECKBOX
        assert content == "Item checkbox"

    def test_detect_numbered(self, detector):
        """Teste detecção de numerada."""
        list_type, marker, content = detector.detect_list_type("1) Primeiro")
        assert list_type == ListType.NUMBERED
        assert marker == "1"
        assert content == "Primeiro"

    def test_detect_lettered(self, detector):
        """Teste detecção de letras."""
        list_type, marker, content = detector.detect_list_type("a) Item A")
        assert list_type == ListType.LETTERED
        assert marker == "a"
        assert content == "Item A"

    def test_detect_roman(self, detector):
        """Teste detecção de romanos."""
        list_type, marker, content = detector.detect_list_type("ii. Segundo")
        assert list_type == ListType.ROMAN
        assert marker == "ii"
        assert content == "Segundo"

    def test_detect_section_as_none(self, detector):
        """Teste que número de seção é detectado como NONE."""
        list_type, marker, content = detector.detect_list_type("1.1 – Título")
        assert list_type == ListType.NONE

    def test_detect_regular_text_as_none(self, detector):
        """Teste que texto normal é detectado como NONE."""
        list_type, marker, content = detector.detect_list_type("Texto normal aqui")
        assert list_type == ListType.NONE


class TestListDetectorFormatItem:
    """Testes para formatação de itens de lista."""

    @pytest.fixture
    def detector(self):
        return ListDetector()

    def test_format_bullet(self, detector):
        """Teste formatação de bullet."""
        result = detector.format_list_item("• Item de teste")
        assert result == "- Item de teste"

    def test_format_wingdings_checkbox(self, detector):
        """Teste formatação de checkbox Wingdings."""
        result = detector.format_list_item("\uf0fc Ação de fluidos")
        assert result == "- Ação de fluidos"

    def test_format_numbered(self, detector):
        """Teste formatação de numerada."""
        result = detector.format_list_item("1) Primeiro item")
        assert result == "1. Primeiro item"

    def test_format_lettered(self, detector):
        """Teste formatação com letras."""
        result = detector.format_list_item("a) Item A")
        assert result == "a) Item A"

    def test_format_with_level(self, detector):
        """Teste formatação com nível."""
        result = detector.format_list_item("• Sub-item", level=1)
        assert result == "  - Sub-item"

    def test_format_regular_text_unchanged(self, detector):
        """Teste que texto normal não é alterado."""
        result = detector.format_list_item("Texto normal")
        assert result == "Texto normal"


class TestListDetectorInlineList:
    """Testes para detecção de listas inline."""

    @pytest.fixture
    def detector(self):
        return ListDetector()

    def test_has_inline_list_with_semicolons(self, detector):
        """Teste detecção de lista inline com ponto-e-vírgula."""
        text = "São áreas:   Item1;   Item2;   Item3;"
        assert detector.has_inline_list(text)

    def test_has_inline_list_false_for_normal(self, detector):
        """Teste que texto normal não é lista inline."""
        text = "Este é um texto normal sem lista."
        assert not detector.has_inline_list(text)

    def test_has_inline_list_false_short(self, detector):
        """Teste que texto curto não é lista inline."""
        text = "Curto"
        assert not detector.has_inline_list(text)

    def test_extract_inline_list(self, detector):
        """Teste extração de lista inline."""
        text = "Áreas de atuação:   Item1;   Item2;   Item3;"
        intro, items = detector.extract_inline_list(text)
        assert "Áreas" in intro
        assert len(items) >= 2

    def test_process_paragraph_with_inline_list(self, detector):
        """Teste processamento de parágrafo com lista inline."""
        text = "Conceitos:   Primeiro;   Segundo;   Terceiro;"
        result = detector.process_paragraph(text)
        assert "-" in result or "Primeiro" in result


class TestListDetectorProcessBlocks:
    """Testes para processamento de blocos de texto."""

    @pytest.fixture
    def detector(self):
        return ListDetector()

    def test_process_blocks_with_list(self, detector):
        """Teste processamento de blocos com lista."""
        blocks = [
            "Introdução ao tema:",
            "• Primeiro item",
            "• Segundo item",
            "• Terceiro item",
            "Conclusão do texto.",
        ]
        result = detector.process_blocks(blocks)
        assert any("- Primeiro" in line for line in result)
        assert any("- Segundo" in line for line in result)
        assert any("- Terceiro" in line for line in result)

    def test_process_blocks_empty(self, detector):
        """Teste processamento de lista vazia."""
        result = detector.process_blocks([])
        assert result == []

    def test_process_blocks_no_list(self, detector):
        """Teste processamento sem lista."""
        blocks = ["Texto normal.", "Outro texto."]
        result = detector.process_blocks(blocks)
        assert len(result) == 2


class TestConvenienceFunctions:
    """Testes para funções de conveniência."""

    def test_get_list_detector_singleton(self):
        """Teste que get_list_detector retorna singleton."""
        d1 = get_list_detector()
        d2 = get_list_detector()
        assert d1 is d2

    def test_is_list_item_function(self):
        """Teste função is_list_item."""
        assert is_list_item("• Item")
        assert not is_list_item("Texto normal")

    def test_format_list_item_function(self):
        """Teste função format_list_item."""
        result = format_list_item("• Item")
        assert result == "- Item"

    def test_process_paragraph_lists_function(self):
        """Teste função process_paragraph_lists."""
        text = "• Item de lista"
        result = process_paragraph_lists(text)
        assert "- Item" in result


class TestRealWorldCases:
    """Testes com casos reais do PDF aula1.pdf."""

    @pytest.fixture
    def detector(self):
        return ListDetector()

    def test_wingdings_checkbox_real_case(self, detector):
        """Teste caso real de checkbox Wingdings."""
        text = "\uf0fc  Ação de fluidos sobre superfícies submersas, ex.: barragens;"
        assert detector.is_list_item(text)
        result = detector.format_list_item(text)
        assert "Ação de fluidos" in result
        assert result.startswith("- ")

    def test_multiple_real_items(self, detector):
        """Teste múltiplos itens reais."""
        items = [
            "\uf0fc  Ação de fluidos sobre superfícies submersas, ex.: barragens;",
            "\uf0fc  Equilíbrio de corpos flutuantes, ex.: embarcações;",
            "\uf0fc  Ação do vento sobre construções civis;",
            "\uf0fc  Estudos de lubrificação;",
        ]
        for item in items:
            assert detector.is_list_item(item)
            result = detector.format_list_item(item)
            assert result.startswith("- ")

    def test_section_number_not_list(self, detector):
        """Teste que '1.1 – Mecânica' não é lista."""
        text = "1.1 – Mecânica dos Fluidos"
        assert not detector.is_list_item(text)

    def test_lettered_items_in_pdf(self, detector):
        """Teste itens com letras do PDF."""
        items = [
            "a) massa específica",
            "b) peso específico",
            "c) peso específico relativo",
            "d) volume específico",
            "e) compressibilidade",
        ]
        for item in items:
            assert detector.is_list_item(item)
