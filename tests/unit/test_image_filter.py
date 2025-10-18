import pytest
from app.utils.image_filter import ImageFilter


class TestImageFilterInit:
    """Testes para inicialização do ImageFilter"""

    def test_init_default_values(self):
        """Deve criar com valores padrão"""
        filter = ImageFilter()
        assert filter.page_height == 850
        assert filter.page_width == 595
        assert filter.header_margin_percent == 0.10
        assert filter.footer_margin_percent == 0.10
        assert filter.side_margin_percent == 0.02

    def test_init_custom_values(self):
        """Deve aceitar valores customizados"""
        filter = ImageFilter(page_height=1000, page_width=800)
        assert filter.page_height == 1000
        assert filter.page_width == 800


class TestHeaderFooterDetection:
    """Testes para detecção de cabeçalho e rodapé"""

    def test_image_in_header(self):
        """Deve detectar imagem no cabeçalho"""
        filter = ImageFilter(page_height=850, page_width=595)
        # Primeiros 10% = até 85px
        bbox = (0, 0, 595, 50)
        assert filter.is_header_or_footer(bbox) is True

    def test_image_in_footer(self):
        """Deve detectar imagem no rodapé"""
        filter = ImageFilter(page_height=850, page_width=595)
        # Últimos 10% = de 765px em diante
        bbox = (0, 800, 595, 850)
        assert filter.is_header_or_footer(bbox) is True

    def test_image_in_content(self):
        """Deve permitir imagem no corpo do texto"""
        filter = ImageFilter(page_height=850, page_width=595)
        bbox = (100, 200, 500, 400)
        assert filter.is_header_or_footer(bbox) is False

    def test_image_on_edge_header(self):
        """Deve detectar imagem na borda do cabeçalho"""
        filter = ImageFilter(page_height=850, page_width=595)
        bbox = (0, 0, 595, 85)  # No limite (85px = 10%)
        assert filter.is_header_or_footer(bbox) is True

    def test_image_just_below_header(self):
        """Deve aceitar imagem logo abaixo do cabeçalho"""
        filter = ImageFilter(page_height=850, page_width=595)
        bbox = (0, 86, 595, 200)  # Logo abaixo de 85px
        assert filter.is_header_or_footer(bbox) is False


class TestSideMarginDetection:
    """Testes para detecção de margens laterais"""

    def test_small_image_left_margin(self):
        """Deve detectar imagem pequena na margem esquerda"""
        filter = ImageFilter(page_width=595)
        # Margem esquerda = 2% de 595 = 11.9px
        bbox = (0, 100, 30, 150)  # Pequena, na esquerda
        assert filter.is_side_margin(bbox) is True

    def test_small_image_right_margin(self):
        """Deve detectar imagem pequena na margem direita"""
        filter = ImageFilter(page_width=595)
        # Margem direita começa em 95% = 565px
        bbox = (570, 100, 595, 150)  # Pequena, na direita
        assert filter.is_side_margin(bbox) is True

    def test_large_image_center(self):
        """Não deve detectar imagem grande no centro"""
        filter = ImageFilter(page_width=595)
        bbox = (100, 100, 500, 400)  # Grande, no centro
        assert filter.is_side_margin(bbox) is False

    def test_image_acceptable_left_margin(self):
        """Deve aceitar imagem ampla na esquerda"""
        filter = ImageFilter(page_width=595)
        bbox = (0, 100, 200, 400)  # Ampla (200px), na esquerda
        assert filter.is_side_margin(bbox) is False


class TestImageSize:
    """Testes para análise de tamanho de imagem"""

    def test_get_image_size(self):
        """Deve calcular corretamente dimensões"""
        filter = ImageFilter()
        bbox = (10, 20, 110, 120)
        width, height = filter.get_image_size(bbox)
        assert width == 100
        assert height == 100

    def test_is_too_small_true(self):
        """Deve detectar imagem muito pequena"""
        filter = ImageFilter()
        bbox = (0, 0, 10, 10)  # Área = 100px²
        assert filter.is_too_small(bbox, min_area=3000) is True

    def test_is_too_small_false(self):
        """Deve aceitar imagem de tamanho adequado"""
        filter = ImageFilter()
        bbox = (0, 0, 100, 100)  # Área = 10000px²
        assert filter.is_too_small(bbox, min_area=3000) is False

    def test_is_too_small_boundary(self):
        """Deve lidar com imagem no limite de tamanho"""
        filter = ImageFilter()
        bbox = (0, 0, 100, 30)  # Área = 3000px² (exato)
        assert filter.is_too_small(bbox, min_area=3000) is False


class TestFigureReferences:
    """Testes para detecção de referências a figuras"""

    def test_detect_figura_portuguese(self):
        """Deve detectar 'Figura 1' em português"""
        filter = ImageFilter()
        text = "Como mostra a Figura 1 abaixo..."
        refs = filter.find_figure_references(text)
        assert "figura" in refs
        assert 1 in refs["figura"]

    def test_detect_table_portuguese(self):
        """Deve detectar 'Tabela 3' em português"""
        filter = ImageFilter()
        text = "A Tabela 3 apresenta os resultados..."
        refs = filter.find_figure_references(text)
        assert "tabela" in refs
        assert 3 in refs["tabela"]

    def test_detect_figure_english(self):
        """Deve detectar 'Figure 1' em inglês"""
        filter = ImageFilter()
        text = "As shown in Figure 1..."
        refs = filter.find_figure_references(text)
        assert "figure" in refs
        assert 1 in refs["figure"]

    def test_detect_multiple_figures(self):
        """Deve detectar múltiplas figuras"""
        filter = ImageFilter()
        text = "Figura 1 mostra X. Figura 2 mostra Y."
        refs = filter.find_figure_references(text)
        assert 1 in refs.get("figura", [])
        assert 2 in refs.get("figura", [])

    def test_detect_image_abbreviation(self):
        """Deve detectar 'Img. 5'"""
        filter = ImageFilter()
        text = "Ver Img. 5 para detalhes"
        refs = filter.find_figure_references(text)
        # Pode ser detectado como 'img' ou similar
        assert len(refs) > 0

    def test_no_references(self):
        """Deve retornar vazio quando sem referências"""
        filter = ImageFilter()
        text = "Texto sem nenhuma figura ou tabela"
        refs = filter.find_figure_references(text)
        assert refs == {}

    def test_case_insensitive_detection(self):
        """Deve detectar independente de maiúscula/minúscula"""
        filter = ImageFilter()
        text = "FIGURA 1 E figura 2"
        refs = filter.find_figure_references(text)
        assert "figura" in refs
        assert 1 in refs["figura"]
        assert 2 in refs["figura"]


class TestRelevanceDecision:
    """Testes para decisão de relevância de imagem"""

    def test_header_not_relevant(self):
        """Cabeçalho nunca deve ser relevante"""
        filter = ImageFilter()
        bbox = (0, 0, 595, 50)  # No cabeçalho
        assert filter.is_relevant_image(bbox) is False

    def test_footer_not_relevant(self):
        """Rodapé nunca deve ser relevante"""
        filter = ImageFilter()
        bbox = (0, 800, 595, 850)  # No rodapé
        assert filter.is_relevant_image(bbox) is False

    def test_small_image_not_relevant(self):
        """Imagem muito pequena não deve ser relevante"""
        filter = ImageFilter()
        bbox = (0, 0, 10, 10)  # Muito pequena
        assert filter.is_relevant_image(bbox) is False

    def test_large_centered_image_relevant(self):
        """Imagem grande no centro deve ser relevante"""
        filter = ImageFilter()
        bbox = (100, 200, 500, 400)  # Grande no centro
        assert filter.is_relevant_image(bbox) is True

    def test_image_with_figure_reference_relevant(self):
        """Imagem em página com referência a figura deve ser relevante"""
        filter = ImageFilter()
        bbox = (100, 200, 500, 400)
        page_text = "Figura 1 mostra..."
        assert filter.is_relevant_image(
            bbox,
            page_text=page_text,
            has_figure_reference=True
        ) is True

    def test_boundary_size_image_relevant(self):
        """Imagem no limite de tamanho deve ser relevante"""
        filter = ImageFilter()
        bbox = (100, 200, 300, 350)  # Área = ~15000px² (200x150)
        assert filter.is_relevant_image(bbox) is True


class TestBboxOverlap:
    """Testes para detecção de sobreposição de bbox"""

    def test_bboxes_overlap(self):
        """Deve detectar sobreposição"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (50, 50, 150, 150)
        result = ImageFilter._bboxes_overlap_or_near(bbox1, bbox2)
        assert result is True

    def test_bboxes_not_overlap(self):
        """Deve detectar quando não há sobreposição"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (200, 200, 300, 300)
        result = ImageFilter._bboxes_overlap_or_near(bbox1, bbox2)
        assert result is False

    def test_bboxes_adjacent(self):
        """Deve detectar bboxes adjacentes"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (100, 0, 200, 100)
        result = ImageFilter._bboxes_overlap_or_near(bbox1, bbox2)
        assert result is True  # Adjacentes são considerados próximos (não há gap)

    def test_bboxes_near_with_tolerance(self):
        """Deve considerar proximidade com tolerância"""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (110, 0, 200, 100)
        result = ImageFilter._bboxes_overlap_or_near(bbox1, bbox2, tolerance=20)
        assert result is True

    def test_bbox_contains_other(self):
        """Deve detectar quando um bbox contém o outro"""
        bbox1 = (0, 0, 200, 200)
        bbox2 = (50, 50, 100, 100)
        result = ImageFilter._bboxes_overlap_or_near(bbox1, bbox2)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
