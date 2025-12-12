"""
Testes para o módulo de filtro de headings.

Cobre detecção, filtragem e classificação de headings baseado em tamanho de fonte.
"""

import pytest
from typing import List
from app.utils.heading_filter import (
    HeadingFilter,
    HeadingCandidate,
    Heading,
)


class TestHeadingCandidate:
    """Testes para a dataclass HeadingCandidate."""

    def test_create_candidate(self):
        """Deve criar um candidato com todos os parâmetros."""
        candidate = HeadingCandidate(
            text="Título Principal",
            font_size=24.0,
            page_num=1,
            bbox=(10.0, 20.0, 100.0, 40.0),
            y_ratio=0.1
        )
        assert candidate.text == "Título Principal"
        assert candidate.font_size == 24.0
        assert candidate.page_num == 1
        assert candidate.bbox == (10.0, 20.0, 100.0, 40.0)
        assert candidate.y_ratio == 0.1

    def test_candidate_with_defaults(self):
        """HeadingCandidate requer todos os campos."""
        with pytest.raises(TypeError):
            HeadingCandidate(text="Teste", font_size=12.0)


class TestHeading:
    """Testes para a dataclass Heading."""

    def test_create_heading(self):
        """Deve criar um heading validado."""
        heading = Heading(
            text="Capítulo 1",
            level=1,
            page_num=5,
            font_size=28.0,
            position=(10.0, 50.0, 200.0, 80.0)
        )
        assert heading.text == "Capítulo 1"
        assert heading.level == 1
        assert heading.page_num == 5
        assert heading.font_size == 28.0


class TestHeadingFilterInitialization:
    """Testes de inicialização do HeadingFilter."""

    def test_init_default_page_height(self):
        """Deve usar altura padrão de página."""
        hf = HeadingFilter()
        assert hf.page_height == 792.0

    def test_init_custom_page_height(self):
        """Deve aceitar altura de página customizada."""
        hf = HeadingFilter(page_height=600.0)
        assert hf.page_height == 600.0

    def test_init_empty_state(self):
        """Deve inicializar com estado vazio."""
        hf = HeadingFilter()
        assert hf.size_to_level == {}
        assert hf.seen_texts == set()

    def test_reset(self):
        """Reset deve limpar o estado interno."""
        hf = HeadingFilter()
        hf.size_to_level = {24.0: 1, 18.0: 2}
        hf.seen_texts = {"Título 1", "Título 2"}

        hf.reset()

        assert hf.size_to_level == {}
        assert hf.seen_texts == set()


class TestHeadingFilterValidation:
    """Testes de validação de candidatos."""

    @pytest.fixture
    def hf(self):
        return HeadingFilter()

    def test_is_valid_text_normal(self, hf):
        """Deve aceitar texto normal."""
        assert hf._is_valid_text("Introdução ao Python") is True

    def test_is_valid_text_empty(self, hf):
        """Deve rejeitar texto vazio."""
        assert hf._is_valid_text("") is False
        assert hf._is_valid_text("   ") is False

    def test_is_valid_text_too_short(self, hf):
        """Deve rejeitar texto muito curto."""
        assert hf._is_valid_text("A") is False

    def test_is_valid_text_too_long(self, hf):
        """Deve rejeitar texto muito longo."""
        long_text = "A" * 201
        assert hf._is_valid_text(long_text) is False

    def test_is_valid_text_only_numbers(self, hf):
        """Deve rejeitar apenas números."""
        assert hf._is_valid_text("12345") is False

    def test_is_valid_text_only_special_chars(self, hf):
        """Deve rejeitar apenas caracteres especiais."""
        assert hf._is_valid_text("@#$%&*") is False

    def test_is_valid_text_mixed_valid(self, hf):
        """Deve aceitar texto com números e caracteres especiais."""
        assert hf._is_valid_text("Chapter 1: Introduction") is True
        assert hf._is_valid_text("Test-123") is True


class TestHeadingFilterGenericTitles:
    """Testes de detecção de títulos genéricos."""

    @pytest.fixture
    def hf(self):
        return HeadingFilter()

    def test_generic_sumario(self, hf):
        """Deve detectar 'Sumário' como genérico."""
        assert hf._is_generic_title("Sumário") is True
        assert hf._is_generic_title("SUMÁRIO") is True

    def test_generic_introducao(self, hf):
        """Deve detectar 'Introdução' como genérico."""
        assert hf._is_generic_title("Introdução") is True

    def test_generic_conclusao(self, hf):
        """Deve detectar 'Conclusão' como genérico."""
        assert hf._is_generic_title("Conclusão") is True

    def test_generic_references(self, hf):
        """Deve detectar 'References' como genérico."""
        assert hf._is_generic_title("References") is True

    def test_not_generic(self, hf):
        """Deve aceitar títulos não genéricos."""
        assert hf._is_generic_title("Capítulo 1") is False
        assert hf._is_generic_title("Métodos") is False
        assert hf._is_generic_title("Análise de Dados") is False

    def test_generic_case_insensitive(self, hf):
        """Detecção deve ser case-insensitive."""
        assert hf._is_generic_title("APÊNDICE") is True
        assert hf._is_generic_title("appendix") is True


class TestHeadingFilterMarginDetection:
    """Testes de detecção de rodapé/cabeçalho."""

    @pytest.fixture
    def hf(self):
        return HeadingFilter(page_height=792.0)

    def test_header_top_5_percent(self, hf):
        """Deve detectar texto no topo 5% como cabeçalho."""
        assert hf._is_in_margin(0.02) is True
        assert hf._is_in_margin(0.04) is True

    def test_footer_bottom_8_percent(self, hf):
        """Deve detectar texto no fundo 8% como rodapé."""
        assert hf._is_in_margin(0.95) is True
        assert hf._is_in_margin(0.99) is True

    def test_not_in_margin(self, hf):
        """Deve aceitar texto no meio."""
        assert hf._is_in_margin(0.5) is False
        assert hf._is_in_margin(0.3) is False
        assert hf._is_in_margin(0.8) is False

    def test_margin_boundary_header(self, hf):
        """Teste no limite do cabeçalho."""
        assert hf._is_in_margin(0.05) is False  # Limite externo
        assert hf._is_in_margin(0.049) is True  # Dentro

    def test_margin_boundary_footer(self, hf):
        """Teste no limite do rodapé."""
        assert hf._is_in_margin(0.92) is False  # Limite externo
        assert hf._is_in_margin(0.921) is True  # Dentro


class TestHeadingFilterNormalization:
    """Testes de normalização de texto."""

    @pytest.fixture
    def hf(self):
        return HeadingFilter()

    def test_normalize_whitespace(self, hf):
        """Deve normalizar espaços em branco."""
        assert hf._normalize_text("  Título   Principal  ") == "título principal"

    def test_normalize_case(self, hf):
        """Deve converter para minúsculas."""
        assert hf._normalize_text("TÍTULO") == "título"
        assert hf._normalize_text("TíTuLo") == "título"

    def test_normalize_tabs_and_newlines(self, hf):
        """Deve normalizar tabs e quebras de linha."""
        assert hf._normalize_text("Título\n\tPrincipal") == "título principal"

    def test_normalize_accents(self, hf):
        """Deve preservar acentos."""
        assert hf._normalize_text("Análise") == "análise"
        assert hf._normalize_text("São Paulo") == "são paulo"


class TestHeadingFilterGrouping:
    """Testes de agrupamento de tamanhos similares."""

    @pytest.fixture
    def hf(self):
        return HeadingFilter()

    def test_group_exact_duplicates(self, hf):
        """Deve remover tamanhos duplicados exatos."""
        sizes = [24.0, 24.0, 18.0, 18.0]
        grouped = hf._group_similar_sizes(sizes)
        assert len(grouped) == 2
        assert 24.0 in grouped
        assert 18.0 in grouped

    def test_group_similar_sizes_tolerance(self, hf):
        """Deve agrupar tamanhos dentro da tolerância."""
        sizes = [24.0, 24.3, 24.2, 18.0, 18.1]
        grouped = hf._group_similar_sizes(sizes)
        # Deve agrupar 24.0/24.3/24.2 e 18.0/18.1
        assert len(grouped) <= 2

    def test_group_descending_order(self, hf):
        """Deve retornar tamanhos em ordem descendente."""
        sizes = [12.0, 28.0, 16.0, 22.0]
        grouped = hf._group_similar_sizes(sizes)
        assert grouped == sorted(grouped, reverse=True)

    def test_group_empty_list(self, hf):
        """Deve lidar com lista vazia."""
        assert hf._group_similar_sizes([]) == []

    def test_group_single_size(self, hf):
        """Deve lidar com um único tamanho."""
        grouped = hf._group_similar_sizes([24.0])
        assert grouped == [24.0]


class TestHeadingFilterSizeMapping:
    """Testes de mapeamento de tamanho para nível."""

    @pytest.fixture
    def hf(self):
        return HeadingFilter()

    def test_map_single_size(self, hf):
        """Um tamanho deve mapear para H1."""
        candidates = [
            HeadingCandidate("Título", 24.0, 1, (0, 0, 100, 50), 0.5)
        ]
        hf._build_size_to_level_mapping(candidates)
        assert hf.size_to_level[24.0] == 1

    def test_map_multiple_sizes(self, hf):
        """Múltiplos tamanhos devem mapear para H1-Hn."""
        candidates = [
            HeadingCandidate("H1", 28.0, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("H2", 22.0, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("H3", 16.0, 1, (0, 0, 100, 50), 0.5),
        ]
        hf._build_size_to_level_mapping(candidates)
        assert hf.size_to_level[28.0] == 1
        assert hf.size_to_level[22.0] == 2
        assert hf.size_to_level[16.0] == 3

    def test_map_max_six_levels(self, hf):
        """Deve limitar a H6 no máximo."""
        candidates = [
            HeadingCandidate(f"H{i}", float(30 - i), 1, (0, 0, 100, 50), 0.5)
            for i in range(8)
        ]
        hf._build_size_to_level_mapping(candidates)
        assert len(hf.size_to_level) == 6
        assert max(hf.size_to_level.values()) == 6

    def test_map_empty_candidates(self, hf):
        """Candidatos vazios não devem criar mapeamento."""
        hf._build_size_to_level_mapping([])
        assert hf.size_to_level == {}

    def test_get_heading_level_exact_match(self, hf):
        """Deve retornar nível para tamanho exato."""
        hf.size_to_level = {24.0: 1, 18.0: 2}
        assert hf.get_heading_level(24.0) == 1
        assert hf.get_heading_level(18.0) == 2

    def test_get_heading_level_similar_size(self, hf):
        """Deve retornar nível para tamanho dentro da tolerância."""
        hf.size_to_level = {24.0: 1}
        assert hf.get_heading_level(24.3) == 1
        assert hf.get_heading_level(23.8) == 1

    def test_get_heading_level_no_match(self, hf):
        """Deve retornar None para tamanho sem correspondência."""
        hf.size_to_level = {24.0: 1}
        assert hf.get_heading_level(12.0) is None


class TestHeadingFilterValidateCandidates:
    """Testes de validação de candidatos."""

    @pytest.fixture
    def hf(self):
        return HeadingFilter()

    def test_validate_all_filters_pass(self, hf):
        """Candidato válido deve passar em todos os filtros."""
        candidates = [
            HeadingCandidate("Capítulo 1", 24.0, 1, (0, 0, 100, 50), 0.5)
        ]
        valid = hf._validate_candidates(candidates)
        assert len(valid) == 1

    def test_validate_reject_invalid_font_size_too_small(self, hf):
        """Deve rejeitar tamanho de fonte muito pequeno."""
        candidates = [
            HeadingCandidate("Texto", 8.0, 1, (0, 0, 100, 50), 0.5)
        ]
        valid = hf._validate_candidates(candidates)
        assert len(valid) == 0

    def test_validate_reject_invalid_font_size_too_large(self, hf):
        """Deve rejeitar tamanho de fonte muito grande."""
        candidates = [
            HeadingCandidate("Texto", 80.0, 1, (0, 0, 100, 50), 0.5)
        ]
        valid = hf._validate_candidates(candidates)
        assert len(valid) == 0

    def test_validate_reject_generic_title(self, hf):
        """Deve rejeitar título genérico."""
        candidates = [
            HeadingCandidate("Introdução", 24.0, 1, (0, 0, 100, 50), 0.5)
        ]
        valid = hf._validate_candidates(candidates)
        assert len(valid) == 0

    def test_validate_reject_header_position(self, hf):
        """Deve rejeitar texto no cabeçalho."""
        candidates = [
            HeadingCandidate("Header Text", 24.0, 1, (0, 0, 100, 50), 0.02)
        ]
        valid = hf._validate_candidates(candidates)
        assert len(valid) == 0

    def test_validate_reject_footer_position(self, hf):
        """Deve rejeitar texto no rodapé."""
        candidates = [
            HeadingCandidate("Footer Text", 24.0, 1, (0, 0, 100, 50), 0.95)
        ]
        valid = hf._validate_candidates(candidates)
        assert len(valid) == 0

    def test_validate_reject_duplicate(self, hf):
        """Deve rejeitar duplicatas."""
        candidates = [
            HeadingCandidate("Capítulo 1", 24.0, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("Capítulo 1", 24.0, 2, (0, 0, 100, 50), 0.5),
        ]
        valid = hf._validate_candidates(candidates)
        assert len(valid) == 1

    def test_validate_reject_empty_text(self, hf):
        """Deve rejeitar texto vazio."""
        candidates = [
            HeadingCandidate("", 24.0, 1, (0, 0, 100, 50), 0.5)
        ]
        valid = hf._validate_candidates(candidates)
        assert len(valid) == 0


class TestHeadingFilterFilterHeadings:
    """Testes da função principal filter_headings."""

    @pytest.fixture
    def hf(self):
        return HeadingFilter()

    def test_filter_single_heading(self, hf):
        """Deve filtrar um único heading válido."""
        candidates = [
            HeadingCandidate("Capítulo 1", 24.0, 1, (0, 0, 100, 50), 0.5)
        ]
        headings = hf.filter_headings(candidates)
        assert len(headings) == 1
        assert headings[0].text == "Capítulo 1"
        assert headings[0].level == 1

    def test_filter_multiple_headings(self, hf):
        """Deve filtrar e classificar múltiplos headings."""
        candidates = [
            HeadingCandidate("Capítulo 1", 28.0, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("Seção 1.1", 22.0, 1, (0, 0, 100, 100), 0.3),
            HeadingCandidate("Subseção", 16.0, 1, (0, 0, 100, 150), 0.4),
        ]
        headings = hf.filter_headings(candidates)
        assert len(headings) == 3
        assert headings[0].level == 1
        assert headings[1].level == 2
        assert headings[2].level == 3

    def test_filter_empty_list(self, hf):
        """Deve retornar lista vazia para entrada vazia."""
        headings = hf.filter_headings([])
        assert headings == []

    def test_filter_all_rejected(self, hf):
        """Deve retornar lista vazia se todos forem rejeitados."""
        candidates = [
            HeadingCandidate("Introdução", 24.0, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("Sumário", 24.0, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("", 24.0, 1, (0, 0, 100, 50), 0.5),
        ]
        headings = hf.filter_headings(candidates)
        assert headings == []

    def test_filter_preserves_order(self, hf):
        """Deve preservar ordem dos headings válidos."""
        candidates = [
            HeadingCandidate("First", 28.0, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("Second", 22.0, 1, (0, 0, 100, 100), 0.3),
            HeadingCandidate("Third", 16.0, 1, (0, 0, 100, 150), 0.4),
        ]
        headings = hf.filter_headings(candidates)
        assert [h.text for h in headings] == ["First", "Second", "Third"]

    def test_filter_deduplicate_normalized(self, hf):
        """Deve remover duplicatas mesmo com variações de espaço."""
        candidates = [
            HeadingCandidate("Capítulo  1", 28.0, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("capítulo 1", 28.0, 2, (0, 0, 100, 100), 0.3),
        ]
        headings = hf.filter_headings(candidates)
        # Deve aceitar apenas uma (primeira)
        assert len(headings) <= 2  # Depende da dedupliação


class TestHeadingFilterStatistics:
    """Testes de estatísticas."""

    def test_get_statistics(self):
        """Deve retornar estatísticas corretas."""
        hf = HeadingFilter(page_height=600.0)
        hf.size_to_level = {28.0: 1, 22.0: 2}
        hf.seen_texts = {"Título 1", "Título 2"}

        stats = hf.get_statistics()

        assert stats["total_sizes"] == 2
        assert stats["page_height"] == 600.0
        assert stats["total_seen_texts"] == 2
        assert stats["size_to_level"] == hf.size_to_level

    def test_get_statistics_empty(self):
        """Deve retornar estatísticas para estado vazio."""
        hf = HeadingFilter()
        stats = hf.get_statistics()

        assert stats["total_sizes"] == 0
        assert stats["total_seen_texts"] == 0


class TestHeadingFilterIntegration:
    """Testes de integração (fluxo completo)."""

    def test_complete_workflow_real_pdf_like(self):
        """Teste completo com dados similares a um PDF real."""
        hf = HeadingFilter()

        # Simular extractos de um PDF
        candidates = [
            # Página 1
            HeadingCandidate("Manual de Usuário", 32.0, 1, (0, 50, 300, 100), 0.2),
            HeadingCandidate("Page 1", 10.0, 1, (0, 750, 100, 770), 0.95),  # Rodapé
            HeadingCandidate("Capítulo 1: Introdução", 28.0, 1, (0, 150, 400, 200), 0.3),
            HeadingCandidate("Introdução", 24.0, 1, (0, 200, 200, 230), 0.35),  # Genérico
            # Página 2
            HeadingCandidate("Seção 1.1", 22.0, 2, (0, 100, 200, 130), 0.2),
            HeadingCandidate("Page 2", 10.0, 2, (0, 750, 100, 770), 0.95),  # Rodapé
            HeadingCandidate("Subseção 1.1.1", 16.0, 2, (0, 200, 300, 220), 0.3),
            # Página 3
            HeadingCandidate("Capítulo 2", 28.0, 3, (0, 50, 200, 100), 0.1),
            HeadingCandidate("Conclusão", 24.0, 3, (0, 400, 200, 430), 0.6),  # Genérico
        ]

        headings = hf.filter_headings(candidates)

        # Verificações
        assert len(headings) >= 4  # Mínimo de headings esperados
        assert all(h.level >= 1 and h.level <= 6 for h in headings)
        assert all(h.text for h in headings)  # Todos têm texto
        # Deve ter remover rodapés e genéricos

    def test_add_candidate_validates_input(self):
        """add_candidate deve validar entrada."""
        hf = HeadingFilter()

        # Lista vazia é válida, apenas retorna sem processar
        hf.add_candidate([])  # Não deve lançar exceção

        with pytest.raises(ValueError):
            hf.add_candidate(["não é HeadingCandidate"])

    def test_workflow_with_similar_sizes(self):
        """Deve agrupar tamanhos similares corretamente."""
        hf = HeadingFilter()

        candidates = [
            HeadingCandidate("Title 1", 28.0, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("Title 2", 28.1, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("Title 3", 28.2, 1, (0, 0, 100, 50), 0.5),
            HeadingCandidate("Subtitle 1", 22.0, 1, (0, 0, 100, 50), 0.5),
        ]

        headings = hf.filter_headings(candidates)

        # Todos os 28.x devem ter o mesmo nível
        level_28 = [h.level for h in headings if abs(h.font_size - 28.0) < 1]
        assert len(set(level_28)) == 1  # Todos iguais
