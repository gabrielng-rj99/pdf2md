"""
Testes unitários para o módulo math_zone_detector.

Testa a detecção de zonas matemáticas em blocos de texto.
"""

import pytest
from app.utils.math_zone_detector import (
    MathZoneDetector,
    MathZoneConfig,
    MathZone,
    ZoneType,
    get_math_zone_detector,
    detect_math_zones_in_text,
    MATH_CHARS,
    MATH_PATTERNS,
)


class TestMathZoneDetector:
    """Testes para a classe MathZoneDetector."""

    def test_init_default_config(self):
        """Testa inicialização com configuração padrão."""
        detector = MathZoneDetector()
        assert detector.config is not None
        assert detector.config.min_confidence == 0.4
        assert detector.config.min_math_density == 0.15

    def test_init_custom_config(self):
        """Testa inicialização com configuração personalizada."""
        config = MathZoneConfig(min_confidence=0.6, min_math_density=0.2)
        detector = MathZoneDetector(config)
        assert detector.config.min_confidence == 0.6
        assert detector.config.min_math_density == 0.2

    def test_is_math_text_with_equation(self):
        """Testa detecção de texto com equação."""
        detector = MathZoneDetector()

        # Equação simples
        is_math, score = detector.is_math_text("f(x) = 2x + 1")
        assert is_math is True
        assert score > 0.4

    def test_is_math_text_with_greek(self):
        """Testa detecção de texto com letras gregas."""
        detector = MathZoneDetector()

        is_math, score = detector.is_math_text("α + β = γ")
        assert is_math is True
        assert score > 0.4

    def test_is_math_text_with_operators(self):
        """Testa detecção de texto com operadores matemáticos."""
        detector = MathZoneDetector()

        is_math, score = detector.is_math_text("∑ x² + ∫ y dy")
        assert is_math is True
        assert score > 0.5

    def test_is_math_text_plain_text(self):
        """Testa que texto normal não é detectado como matemática."""
        detector = MathZoneDetector()

        is_math, score = detector.is_math_text("Este é um texto normal sem matemática.")
        assert is_math is False or score < 0.4

    def test_is_math_text_short_text(self):
        """Testa comportamento com texto muito curto."""
        detector = MathZoneDetector()

        is_math, score = detector.is_math_text("x")
        assert score == 0.0  # Texto muito curto

    def test_is_math_text_empty(self):
        """Testa comportamento com texto vazio."""
        detector = MathZoneDetector()

        is_math, score = detector.is_math_text("")
        assert is_math is False
        assert score == 0.0

    def test_detect_zones_in_blocks_with_math(self):
        """Testa detecção de zonas em blocos com matemática."""
        detector = MathZoneDetector()

        blocks = [
            {
                'text': 'f(x) = x² + 2x + 1',
                'bbox': (100, 100, 300, 120),
                'font_name': 'Times-Roman',
            },
            {
                'text': 'Este é um parágrafo normal.',
                'bbox': (50, 150, 500, 170),
                'font_name': 'Times-Roman',
            },
        ]

        zones = detector.detect_zones_in_blocks(blocks, page_num=1)

        # Deve detectar pelo menos uma zona matemática
        assert len(zones) >= 1
        assert zones[0].zone_type in (ZoneType.EQUATION, ZoneType.INLINE, ZoneType.DISPLAY)

    def test_detect_zones_with_math_font(self):
        """Testa detecção com fonte matemática."""
        detector = MathZoneDetector()

        blocks = [
            {
                'text': 'x + y = z',
                'bbox': (100, 100, 200, 120),
                'font_name': 'Cambria Math',
            },
        ]

        zones = detector.detect_zones_in_blocks(blocks, page_num=1)

        assert len(zones) >= 1
        assert 'math_font' in ' '.join(zones[0].hints)

    def test_detect_zones_centered_formula(self):
        """Testa detecção de fórmula centralizada."""
        detector = MathZoneDetector()

        page_width = 612.0
        center_x = page_width / 2

        blocks = [
            {
                'text': '∫ f(x) dx = F(x) + C',
                'bbox': (center_x - 50, 300, center_x + 50, 320),
                'font_name': 'Times-Roman',
            },
        ]

        zones = detector.detect_zones_in_blocks(blocks, page_num=1, page_width=page_width)

        assert len(zones) >= 1
        # Pode ser detectada como DISPLAY por estar centralizada
        assert zones[0].zone_type in (ZoneType.DISPLAY, ZoneType.EQUATION, ZoneType.INLINE)

    def test_detect_fraction_pattern(self):
        """Testa detecção de padrão de fração."""
        detector = MathZoneDetector()

        blocks = [
            {
                'text': 'a/b + c/d',
                'bbox': (100, 100, 200, 120),
                'font_name': '',
            },
        ]

        zones = detector.detect_zones_in_blocks(blocks, page_num=1)

        assert len(zones) >= 1
        assert any('fraction' in hint for hint in zones[0].hints)

    def test_detect_function_pattern(self):
        """Testa detecção de padrão de função."""
        detector = MathZoneDetector()

        blocks = [
            {
                'text': 'g(x) = sen(x) + cos(x)',
                'bbox': (100, 100, 300, 120),
                'font_name': '',
            },
        ]

        zones = detector.detect_zones_in_blocks(blocks, page_num=1)

        assert len(zones) >= 1

    def test_merge_adjacent_zones(self):
        """Testa fusão de zonas adjacentes."""
        config = MathZoneConfig(merge_adjacent=True, merge_threshold=20.0)
        detector = MathZoneDetector(config)

        blocks = [
            {
                'text': 'x² +',
                'bbox': (100, 100, 150, 115),
                'font_name': '',
            },
            {
                'text': '2x + 1',
                'bbox': (155, 100, 220, 115),
                'font_name': '',
            },
        ]

        zones = detector.detect_zones_in_blocks(blocks, page_num=1)

        # Zonas muito próximas podem ser fundidas
        # O número exato depende da implementação
        assert len(zones) >= 1

    def test_stats_tracking(self):
        """Testa rastreamento de estatísticas."""
        detector = MathZoneDetector()
        detector.reset_stats()

        blocks = [{'text': 'x = 1', 'bbox': (0, 0, 50, 20), 'font_name': ''}]
        detector.detect_zones_in_blocks(blocks, page_num=1)

        stats = detector.get_stats()
        assert stats['pages_processed'] == 1

    def test_reset_stats(self):
        """Testa reset de estatísticas."""
        detector = MathZoneDetector()

        blocks = [{'text': 'x = 1', 'bbox': (0, 0, 50, 20), 'font_name': ''}]
        detector.detect_zones_in_blocks(blocks, page_num=1)

        detector.reset_stats()
        stats = detector.get_stats()

        assert stats['pages_processed'] == 0
        assert stats['zones_detected'] == 0


class TestMathZoneConfig:
    """Testes para a classe MathZoneConfig."""

    def test_default_values(self):
        """Testa valores padrão da configuração."""
        config = MathZoneConfig()

        assert config.min_math_density == 0.15
        assert config.min_confidence == 0.4
        assert config.merge_adjacent is True
        assert 'symbol' in config.math_fonts

    def test_custom_values(self):
        """Testa valores personalizados."""
        config = MathZoneConfig(
            min_math_density=0.3,
            min_confidence=0.7,
            merge_adjacent=False,
        )

        assert config.min_math_density == 0.3
        assert config.min_confidence == 0.7
        assert config.merge_adjacent is False


class TestMathZone:
    """Testes para a classe MathZone."""

    def test_creation(self):
        """Testa criação de MathZone."""
        zone = MathZone(
            bbox=(100, 200, 300, 220),
            zone_type=ZoneType.EQUATION,
            confidence=0.85,
            page_num=1,
            hints=['pattern:equation', 'math_density=0.5'],
        )

        assert zone.bbox == (100, 200, 300, 220)
        assert zone.zone_type == ZoneType.EQUATION
        assert zone.confidence == 0.85
        assert zone.page_num == 1
        assert len(zone.hints) == 2

    def test_zone_types(self):
        """Testa tipos de zona."""
        assert ZoneType.INLINE.value == "inline"
        assert ZoneType.DISPLAY.value == "display"
        assert ZoneType.EQUATION.value == "equation"
        assert ZoneType.FRACTION.value == "fraction"
        assert ZoneType.MATRIX.value == "matrix"


class TestFactoryFunction:
    """Testes para função factory."""

    def test_get_math_zone_detector_default(self):
        """Testa factory com configuração padrão."""
        detector = get_math_zone_detector()
        assert isinstance(detector, MathZoneDetector)

    def test_get_math_zone_detector_custom(self):
        """Testa factory com configuração personalizada."""
        config = MathZoneConfig(min_confidence=0.8)
        detector = get_math_zone_detector(config)

        assert detector.config.min_confidence == 0.8


class TestDetectMathZonesInText:
    """Testes para função detect_math_zones_in_text."""

    def test_detect_equation_span(self):
        """Testa detecção de span de equação."""
        text = "Considere a equação f(x) = 2x + 1 para todo x real."

        zones = detect_math_zones_in_text(text)

        # Deve detectar pelo menos a parte da equação
        assert len(zones) >= 1

    def test_detect_multiple_spans(self):
        """Testa detecção de múltiplos spans."""
        text = "Se f(x) = x² e g(x) = 2x, então f(g(x)) = 4x²"

        zones = detect_math_zones_in_text(text)

        # Pode detectar múltiplas zonas
        assert len(zones) >= 1

    def test_no_math_in_text(self):
        """Testa texto sem matemática."""
        text = "Este é um texto completamente normal sem nenhuma expressão."

        zones = detect_math_zones_in_text(text)

        # Não deve detectar nada (ou muito pouco)
        assert len(zones) == 0 or all(z[2] < 0.3 for z in zones)

    def test_fraction_detection(self):
        """Testa detecção de fração."""
        text = "A fração a/b é igual a c/d"

        zones = detect_math_zones_in_text(text)

        assert len(zones) >= 1


class TestMathPatterns:
    """Testes para os padrões regex."""

    def test_fraction_pattern(self):
        """Testa padrão de fração."""
        pattern = MATH_PATTERNS['fraction']

        assert pattern.search("x/y")
        assert pattern.search("a/b")
        assert pattern.search("1/2")
        # Nota: o padrão básico não captura parênteses, apenas variáveis simples

    def test_equation_pattern(self):
        """Testa padrão de equação."""
        pattern = MATH_PATTERNS['equation']

        assert pattern.search("x = 1")
        assert pattern.search("a < b")
        assert pattern.search("f(x) = 2x")

    def test_function_pattern(self):
        """Testa padrão de função."""
        pattern = MATH_PATTERNS['function']

        assert pattern.search("f(x) =")
        assert pattern.search("g(t) =")
        assert pattern.search("y(n) =")

    def test_sqrt_pattern(self):
        """Testa padrão de raiz."""
        pattern = MATH_PATTERNS['sqrt']

        assert pattern.search("√x")
        assert pattern.search("√")
        assert pattern.search("\\sqrt")

    def test_trig_pattern(self):
        """Testa padrão de trigonometria."""
        pattern = MATH_PATTERNS['trig']

        assert pattern.search("sen(x)")
        assert pattern.search("cos(theta)")
        assert pattern.search("tan(α)")

    def test_log_pattern(self):
        """Testa padrão de logaritmo."""
        pattern = MATH_PATTERNS['log']

        assert pattern.search("log(x)")
        assert pattern.search("ln(e)")
        assert pattern.search("exp(x)")


class TestMathChars:
    """Testes para o conjunto de caracteres matemáticos."""

    def test_contains_operators(self):
        """Testa presença de operadores."""
        assert '+' in MATH_CHARS
        assert '-' in MATH_CHARS
        assert '×' in MATH_CHARS
        assert '÷' in MATH_CHARS
        assert '=' in MATH_CHARS

    def test_contains_greek(self):
        """Testa presença de letras gregas."""
        assert 'α' in MATH_CHARS
        assert 'β' in MATH_CHARS
        assert 'π' in MATH_CHARS
        assert 'Σ' in MATH_CHARS

    def test_contains_special(self):
        """Testa presença de símbolos especiais."""
        assert '∞' in MATH_CHARS
        assert '∑' in MATH_CHARS
        assert '∫' in MATH_CHARS
        assert '√' in MATH_CHARS

    def test_contains_subscripts(self):
        """Testa presença de subscritos."""
        assert '₀' in MATH_CHARS
        assert '₁' in MATH_CHARS
        assert '₂' in MATH_CHARS

    def test_contains_superscripts(self):
        """Testa presença de superscritos."""
        assert '²' in MATH_CHARS
        assert '³' in MATH_CHARS
        assert 'ⁿ' in MATH_CHARS
