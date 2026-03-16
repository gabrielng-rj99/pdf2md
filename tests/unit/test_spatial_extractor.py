"""
Testes unitários para o módulo spatial_extractor.

Testa a extração espacial e reordenação de texto de PDFs.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from app.utils.spatial_extractor import (
    SpatialExtractor,
    SpatialExtractorConfig,
    SpatialWord,
    SpatialLine,
    TextElement,
    get_spatial_extractor,
    reorder_formula_text,
    smart_reorder_with_subscripts,
    extract_with_coordinates,
)


class TestSpatialWord:
    """Testes para a classe SpatialWord."""

    def test_creation(self):
        """Testa criação de SpatialWord."""
        word = SpatialWord(
            text="hello",
            x0=10.0,
            y0=100.0,
            x1=50.0,
            y1=120.0,
            font_size=12.0,
            font_name="Times-Roman",
        )

        assert word.text == "hello"
        assert word.x0 == 10.0
        assert word.y0 == 100.0
        assert word.x1 == 50.0
        assert word.y1 == 120.0
        assert word.font_size == 12.0
        assert word.font_name == "Times-Roman"

    def test_width_property(self):
        """Testa propriedade width."""
        word = SpatialWord(text="test", x0=10.0, y0=0.0, x1=60.0, y1=20.0)
        assert word.width == 50.0

    def test_height_property(self):
        """Testa propriedade height."""
        word = SpatialWord(text="test", x0=0.0, y0=100.0, x1=50.0, y1=120.0)
        assert word.height == 20.0

    def test_center_x_property(self):
        """Testa propriedade center_x."""
        word = SpatialWord(text="test", x0=10.0, y0=0.0, x1=50.0, y1=20.0)
        assert word.center_x == 30.0

    def test_center_y_property(self):
        """Testa propriedade center_y."""
        word = SpatialWord(text="test", x0=0.0, y0=100.0, x1=50.0, y1=120.0)
        assert word.center_y == 110.0

    def test_baseline_property(self):
        """Testa propriedade baseline."""
        word = SpatialWord(text="test", x0=0.0, y0=100.0, x1=50.0, y1=120.0)
        # baseline = y0 + height * 0.8 = 100 + 20 * 0.8 = 116
        assert word.baseline == 116.0


class TestSpatialLine:
    """Testes para a classe SpatialLine."""

    def test_empty_line(self):
        """Testa linha vazia."""
        line = SpatialLine()
        assert line.text == ""
        assert line.bbox == (0, 0, 0, 0)

    def test_text_property(self):
        """Testa propriedade text."""
        words = [
            SpatialWord(text="hello", x0=0, y0=0, x1=30, y1=20),
            SpatialWord(text="world", x0=35, y0=0, x1=70, y1=20),
        ]
        line = SpatialLine(words=words)

        assert line.text == "hello world"

    def test_bbox_property(self):
        """Testa propriedade bbox."""
        words = [
            SpatialWord(text="a", x0=10, y0=100, x1=20, y1=120),
            SpatialWord(text="b", x0=50, y0=105, x1=60, y1=115),
        ]
        line = SpatialLine(words=words)

        bbox = line.bbox
        assert bbox[0] == 10  # min x0
        assert bbox[1] == 100  # min y0
        assert bbox[2] == 60  # max x1
        assert bbox[3] == 120  # max y1


class TestSpatialExtractorConfig:
    """Testes para a classe SpatialExtractorConfig."""

    def test_default_values(self):
        """Testa valores padrão da configuração."""
        config = SpatialExtractorConfig()

        assert config.vertical_tolerance == 3.0
        assert config.horizontal_gap_threshold == 10.0
        assert config.extract_mode == TextElement.WORD
        assert config.normalize_spaces is True
        assert config.remove_line_hyphens is True
        assert config.min_text_length == 1

    def test_custom_values(self):
        """Testa valores personalizados."""
        config = SpatialExtractorConfig(
            vertical_tolerance=5.0,
            horizontal_gap_threshold=15.0,
            normalize_spaces=False,
        )

        assert config.vertical_tolerance == 5.0
        assert config.horizontal_gap_threshold == 15.0
        assert config.normalize_spaces is False


class TestSpatialExtractor:
    """Testes para a classe SpatialExtractor."""

    def test_init_default_config(self):
        """Testa inicialização com configuração padrão."""
        extractor = SpatialExtractor()
        assert extractor.config is not None
        assert extractor.config.vertical_tolerance == 3.0

    def test_init_custom_config(self):
        """Testa inicialização com configuração personalizada."""
        config = SpatialExtractorConfig(vertical_tolerance=5.0)
        extractor = SpatialExtractor(config)
        assert extractor.config.vertical_tolerance == 5.0

    def test_reorder_spatially_empty(self):
        """Testa reordenação de lista vazia."""
        extractor = SpatialExtractor()
        result = extractor.reorder_spatially([])
        assert result == []

    def test_reorder_spatially_single_word(self):
        """Testa reordenação de uma única palavra."""
        extractor = SpatialExtractor()
        words = [SpatialWord(text="hello", x0=0, y0=0, x1=50, y1=20)]
        result = extractor.reorder_spatially(words)

        assert len(result) == 1
        assert result[0].text == "hello"

    def test_reorder_spatially_horizontal(self):
        """Testa reordenação horizontal (esquerda para direita)."""
        extractor = SpatialExtractor()
        words = [
            SpatialWord(text="c", x0=200, y0=100, x1=220, y1=120),
            SpatialWord(text="a", x0=0, y0=100, x1=20, y1=120),
            SpatialWord(text="b", x0=100, y0=100, x1=120, y1=120),
        ]
        result = extractor.reorder_spatially(words)

        assert result[0].text == "a"
        assert result[1].text == "b"
        assert result[2].text == "c"

    def test_reorder_spatially_vertical(self):
        """Testa reordenação vertical (cima para baixo)."""
        extractor = SpatialExtractor()
        words = [
            SpatialWord(text="linha3", x0=0, y0=200, x1=50, y1=220),
            SpatialWord(text="linha1", x0=0, y0=0, x1=50, y1=20),
            SpatialWord(text="linha2", x0=0, y0=100, x1=50, y1=120),
        ]
        result = extractor.reorder_spatially(words)

        assert result[0].text == "linha1"
        assert result[1].text == "linha2"
        assert result[2].text == "linha3"

    def test_reorder_spatially_with_tolerance(self):
        """Testa reordenação com tolerância vertical."""
        config = SpatialExtractorConfig(vertical_tolerance=10.0)
        extractor = SpatialExtractor(config)

        # Palavras que estão "quase" na mesma linha (diferença de 5 pixels < tolerância de 10)
        words = [
            SpatialWord(text="b", x0=100, y0=105, x1=150, y1=125),  # Ligeiramente abaixo
            SpatialWord(text="a", x0=0, y0=100, x1=50, y1=120),
        ]
        result = extractor.reorder_spatially(words, tolerance_y=10.0)

        # Com tolerância, devem ser agrupados na mesma linha, ordenados por x
        assert result[0].text == "a"
        assert result[1].text == "b"

    def test_reconstruct_text_empty(self):
        """Testa reconstrução de texto vazio."""
        extractor = SpatialExtractor()
        result = extractor.reconstruct_text([])
        assert result == ""

    def test_reconstruct_text_simple(self):
        """Testa reconstrução de texto simples."""
        extractor = SpatialExtractor()
        words = [
            SpatialWord(text="hello", x0=0, y0=0, x1=50, y1=20),
            SpatialWord(text="world", x0=60, y0=0, x1=110, y1=20),
        ]
        result = extractor.reconstruct_text(words)

        assert result == "hello world"

    def test_reconstruct_text_normalize_spaces(self):
        """Testa normalização de espaços."""
        config = SpatialExtractorConfig(normalize_spaces=True)
        extractor = SpatialExtractor(config)
        words = [
            SpatialWord(text="hello  ", x0=0, y0=0, x1=50, y1=20),
            SpatialWord(text="  world", x0=60, y0=0, x1=110, y1=20),
        ]
        result = extractor.reconstruct_text(words)

        assert "  " not in result  # Espaços duplos removidos

    def test_reconstruct_lines_empty(self):
        """Testa reconstrução de linhas vazias."""
        extractor = SpatialExtractor()
        result = extractor.reconstruct_lines([])
        assert result == []

    def test_reconstruct_lines_single_line(self):
        """Testa reconstrução de uma única linha."""
        extractor = SpatialExtractor()
        words = [
            SpatialWord(text="hello", x0=0, y0=0, x1=50, y1=20),
            SpatialWord(text="world", x0=60, y0=0, x1=110, y1=20),
        ]
        result = extractor.reconstruct_lines(words)

        assert len(result) == 1
        assert result[0].text == "hello world"

    def test_reconstruct_lines_multiple_lines(self):
        """Testa reconstrução de múltiplas linhas."""
        config = SpatialExtractorConfig(vertical_tolerance=5.0)
        extractor = SpatialExtractor(config)
        words = [
            SpatialWord(text="linha1", x0=0, y0=0, x1=50, y1=15),
            SpatialWord(text="linha2", x0=0, y0=100, x1=50, y1=115),
        ]
        result = extractor.reconstruct_lines(words)

        assert len(result) == 2
        assert result[0].text == "linha1"
        assert result[1].text == "linha2"

    def test_stats_tracking(self):
        """Testa rastreamento de estatísticas."""
        extractor = SpatialExtractor()
        extractor.reset_stats()

        words = [SpatialWord(text="test", x0=0, y0=0, x1=50, y1=20)]
        extractor.reconstruct_lines(words)

        stats = extractor.get_stats()
        assert stats['lines_reconstructed'] == 1

    def test_reset_stats(self):
        """Testa reset de estatísticas."""
        extractor = SpatialExtractor()

        words = [SpatialWord(text="test", x0=0, y0=0, x1=50, y1=20)]
        extractor.reconstruct_lines(words)

        extractor.reset_stats()
        stats = extractor.get_stats()

        assert stats['words_extracted'] == 0
        assert stats['lines_reconstructed'] == 0
        assert stats['pages_processed'] == 0


class TestFactoryFunction:
    """Testes para função factory."""

    def test_get_spatial_extractor_default(self):
        """Testa factory com configuração padrão."""
        extractor = get_spatial_extractor()
        assert isinstance(extractor, SpatialExtractor)

    def test_get_spatial_extractor_custom(self):
        """Testa factory com configuração personalizada."""
        config = SpatialExtractorConfig(vertical_tolerance=8.0)
        extractor = get_spatial_extractor(config)

        assert extractor.config.vertical_tolerance == 8.0


class TestSmartReorderWithSubscripts:
    """Testes para função smart_reorder_with_subscripts."""

    def test_empty_list(self):
        """Testa lista vazia."""
        result = smart_reorder_with_subscripts([])
        assert result == ""

    def test_single_word(self):
        """Testa palavra única."""
        words = [SpatialWord(text="x", x0=0, y0=0, x1=10, y1=15, font_size=12)]
        result = smart_reorder_with_subscripts(words)
        assert "x" in result

    def test_normal_text(self):
        """Testa texto normal sem sub/superscritos."""
        words = [
            SpatialWord(text="a", x0=0, y0=0, x1=10, y1=15, font_size=12),
            SpatialWord(text="b", x0=15, y0=0, x1=25, y1=15, font_size=12),
        ]
        result = smart_reorder_with_subscripts(words)
        assert "a" in result
        assert "b" in result


class TestExtractWithCoordinates:
    """Testes para função extract_with_coordinates."""

    @patch('app.utils.spatial_extractor.fitz', None)
    def test_without_fitz(self):
        """Testa comportamento quando fitz não está disponível."""
        # Quando fitz é None, deve retornar lista vazia
        mock_page = Mock()
        extractor = SpatialExtractor()
        result = extractor.extract_words_from_page(mock_page)
        assert result == []


class TestSpatialExtractorWithMockedPage:
    """Testes com página mockada do PyMuPDF."""

    def setup_method(self):
        """Setup para cada teste."""
        self.mock_page = Mock()
        self.mock_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,  # Bloco de texto
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "Hello",
                                    "bbox": [0, 0, 50, 20],
                                    "size": 12.0,
                                    "font": "Times-Roman",
                                    "flags": 0,
                                },
                                {
                                    "text": "World",
                                    "bbox": [55, 0, 100, 20],
                                    "size": 12.0,
                                    "font": "Times-Roman",
                                    "flags": 0,
                                },
                            ]
                        }
                    ]
                }
            ]
        }

    @patch('app.utils.spatial_extractor.fitz')
    def test_extract_words_from_page(self, mock_fitz):
        """Testa extração de palavras de uma página."""
        mock_fitz.return_value = MagicMock()

        extractor = SpatialExtractor()
        words = extractor.extract_words_from_page(self.mock_page)

        assert len(words) == 2
        assert words[0].text == "Hello"
        assert words[1].text == "World"

    @patch('app.utils.spatial_extractor.fitz')
    def test_extract_words_from_bbox(self, mock_fitz):
        """Testa extração de palavras de uma área específica."""
        mock_fitz.return_value = MagicMock()

        extractor = SpatialExtractor()
        words = extractor.extract_words_from_bbox(self.mock_page, (0, 0, 60, 30))

        # Apenas "Hello" está dentro da bbox (center_x = 25)
        hello_words = [w for w in words if w.text == "Hello"]
        assert len(hello_words) == 1

    @patch('app.utils.spatial_extractor.fitz')
    def test_extract_formula_area(self, mock_fitz):
        """Testa extração de área de fórmula."""
        mock_fitz.return_value = MagicMock()

        extractor = SpatialExtractor()
        text = extractor.extract_formula_area(self.mock_page, (0, 0, 200, 50))

        assert "Hello" in text
        assert "World" in text

    @patch('app.utils.spatial_extractor.fitz')
    def test_process_page(self, mock_fitz):
        """Testa processamento completo de página."""
        mock_fitz.return_value = MagicMock()

        extractor = SpatialExtractor()
        result = extractor.process_page(self.mock_page)

        assert 'full_text' in result
        assert 'lines' in result
        assert 'math_texts' in result
        assert "Hello" in result['full_text']

    @patch('app.utils.spatial_extractor.fitz')
    def test_process_page_with_math_zones(self, mock_fitz):
        """Testa processamento com zonas matemáticas."""
        mock_fitz.return_value = MagicMock()

        extractor = SpatialExtractor()
        math_zones = [(0, 0, 100, 30)]
        result = extractor.process_page(self.mock_page, math_zones=math_zones)

        assert len(result['math_texts']) == 1
        assert 'bbox' in result['math_texts'][0]
        assert 'text' in result['math_texts'][0]


class TestTextElement:
    """Testes para o enum TextElement."""

    def test_values(self):
        """Testa valores do enum."""
        assert TextElement.WORD.value == "word"
        assert TextElement.CHAR.value == "char"
        assert TextElement.SPAN.value == "span"


class TestFormulaSpaghetti:
    """Testes específicos para o problema de 'PDF Spaghetti'."""

    def test_reorder_scrambled_formula(self):
        """Testa reordenação de fórmula embaralhada."""
        extractor = SpatialExtractor()

        # Simula caracteres que aparecem fora de ordem no PDF
        # mas devem formar "P1.V1/C1"
        words = [
            SpatialWord(text="V1", x0=30, y0=100, x1=45, y1=115),
            SpatialWord(text="P1", x0=0, y0=100, x1=15, y1=115),
            SpatialWord(text="/", x0=50, y0=100, x1=55, y1=115),
            SpatialWord(text=".", x0=20, y0=100, x1=25, y1=115),
            SpatialWord(text="C1", x0=60, y0=100, x1=75, y1=115),
        ]

        result = extractor.reconstruct_text(words)

        # Após reordenação, deve estar na ordem correta
        assert "P1" in result
        assert result.index("P1") < result.index("V1")
        assert result.index("V1") < result.index("C1")

    def test_reorder_multiline_equation(self):
        """Testa reordenação de equação multilinha."""
        config = SpatialExtractorConfig(vertical_tolerance=5.0)
        extractor = SpatialExtractor(config)

        # Equação em duas linhas: numerador e denominador
        words = [
            SpatialWord(text="a+b", x0=50, y0=100, x1=80, y1=115),  # Numerador
            SpatialWord(text="c+d", x0=50, y0=130, x1=80, y1=145),  # Denominador
        ]

        lines = extractor.reconstruct_lines(words)

        assert len(lines) == 2
        assert "a+b" in lines[0].text
        assert "c+d" in lines[1].text

    def test_subscript_superscript_handling(self):
        """Testa tratamento de subscrito/superscrito."""
        config = SpatialExtractorConfig(vertical_tolerance=3.0)
        extractor = SpatialExtractor(config)

        # x² onde o 2 está ligeiramente acima e menor
        words = [
            SpatialWord(text="x", x0=0, y0=100, x1=10, y1=115, font_size=12),
            SpatialWord(text="2", x0=12, y0=95, x1=18, y1=105, font_size=8),  # Superscrito
        ]

        result = extractor.reconstruct_text(words)

        # Deve conter ambos os caracteres
        assert "x" in result
        assert "2" in result
