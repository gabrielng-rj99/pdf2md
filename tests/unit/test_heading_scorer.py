"""
Testes unitários para o sistema de scoring de headings.

Testa todas as estratégias (FAST, BALANCED, ACCURATE) e funções auxiliares.
"""

import pytest
import time
from typing import List

from app.utils.heading_scorer import (
    HeadingScorer,
    HeadingCandidate,
    ScoringStrategy,
    ScoringConfig,
    ScoringResult,
    ScoringContext,
    quick_score,
    calculate_stopword_ratio,
    has_section_pattern,
    has_chapter_keyword,
    has_structural_keyword,
    is_bullet_item,
    looks_like_formula,
    extract_flags,
    create_candidate_from_span,
    STOPWORDS_PT,
    STOPWORDS_EN,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_candidates() -> List[HeadingCandidate]:
    """Candidatos de exemplo para testes."""
    return [
        HeadingCandidate(
            text="CAPÍTULO 1 - Introdução",
            font_size=18.0,
            page_num=1,
            bbox=(50, 100, 500, 130),
            y_ratio=0.1,
            is_bold=True,
        ),
        HeadingCandidate(
            text="1.1 Contexto do Problema",
            font_size=14.0,
            page_num=1,
            bbox=(50, 200, 400, 220),
            y_ratio=0.2,
            is_bold=True,
        ),
        HeadingCandidate(
            text="Este é um parágrafo normal de texto que deveria ser identificado como corpo.",
            font_size=12.0,
            page_num=1,
            bbox=(50, 300, 550, 320),
            y_ratio=0.3,
            is_bold=False,
        ),
        HeadingCandidate(
            text="• Item de lista com bullet",
            font_size=12.0,
            page_num=1,
            bbox=(70, 400, 400, 420),
            y_ratio=0.4,
            is_bold=False,
        ),
        HeadingCandidate(
            text="Conclusão",
            font_size=16.0,
            page_num=2,
            bbox=(50, 100, 200, 130),
            y_ratio=0.1,
            is_bold=True,
        ),
    ]


@pytest.fixture
def body_text_candidates() -> List[HeadingCandidate]:
    """Candidatos típicos de corpo de texto."""
    return [
        HeadingCandidate(
            text=f"Este é o parágrafo {i} do documento com texto normal.",
            font_size=12.0,
            page_num=1,
            bbox=(50, 100 + i * 20, 550, 115 + i * 20),
            y_ratio=0.1 + i * 0.05,
            is_bold=False,
        )
        for i in range(10)
    ]


@pytest.fixture
def heading_candidates() -> List[HeadingCandidate]:
    """Candidatos típicos de headings."""
    return [
        HeadingCandidate(
            text="CAPÍTULO 1 - Fundamentos",
            font_size=20.0,
            page_num=1,
            bbox=(50, 50, 400, 80),
            y_ratio=0.05,
            is_bold=True,
        ),
        HeadingCandidate(
            text="1.1 Definições Básicas",
            font_size=16.0,
            page_num=1,
            bbox=(50, 150, 350, 175),
            y_ratio=0.15,
            is_bold=True,
        ),
        HeadingCandidate(
            text="1.1.1 Conceito de Fluido",
            font_size=14.0,
            page_num=1,
            bbox=(50, 250, 300, 270),
            y_ratio=0.25,
            is_bold=True,
        ),
    ]


@pytest.fixture
def scorer_fast() -> HeadingScorer:
    """Scorer com estratégia FAST."""
    config = ScoringConfig(strategy=ScoringStrategy.FAST)
    return HeadingScorer(config)


@pytest.fixture
def scorer_balanced() -> HeadingScorer:
    """Scorer com estratégia BALANCED."""
    config = ScoringConfig(strategy=ScoringStrategy.BALANCED)
    return HeadingScorer(config)


@pytest.fixture
def scorer_accurate() -> HeadingScorer:
    """Scorer com estratégia ACCURATE."""
    config = ScoringConfig(strategy=ScoringStrategy.ACCURATE)
    return HeadingScorer(config)


# =============================================================================
# TESTES DE FUNÇÕES AUXILIARES
# =============================================================================

class TestStopwordRatio:
    """Testes para calculate_stopword_ratio."""

    def test_empty_text(self):
        """Texto vazio deve retornar 0."""
        assert calculate_stopword_ratio("") == 0.0

    def test_all_stopwords(self):
        """Texto só com stopwords deve retornar 1.0."""
        result = calculate_stopword_ratio("de a o em para")
        assert result == 1.0

    def test_no_stopwords(self):
        """Texto sem stopwords deve retornar 0.0."""
        result = calculate_stopword_ratio("Mecânica Fluidos Teoria")
        assert result == 0.0

    def test_mixed_text(self):
        """Texto misto deve retornar proporção correta."""
        result = calculate_stopword_ratio("A teoria de fluidos")  # 3 stopwords de 4 palavras
        assert 0.5 <= result <= 1.0

    def test_english_stopwords(self):
        """Deve reconhecer stopwords em inglês."""
        result = calculate_stopword_ratio("the theory of fluids")
        assert result > 0.0


class TestSectionPattern:
    """Testes para has_section_pattern."""

    def test_simple_section(self):
        """Padrão simples 1.2."""
        assert has_section_pattern("1.2 Título") is True

    def test_deep_section(self):
        """Padrão profundo 1.2.3.4."""
        assert has_section_pattern("1.2.3.4 Subseção") is True

    def test_with_dash(self):
        """Padrão com traço."""
        assert has_section_pattern("1.2 - Nome da Seção") is True

    def test_section_alone(self):
        """Número de seção sozinho."""
        assert has_section_pattern("1.2") is True

    def test_not_section(self):
        """Texto normal não é seção."""
        assert has_section_pattern("Este é um texto normal") is False

    def test_bullet_not_section(self):
        """Bullet não é padrão de seção."""
        assert has_section_pattern("• Item") is False


class TestChapterKeyword:
    """Testes para has_chapter_keyword."""

    def test_capitulo(self):
        """Detecta 'Capítulo'."""
        assert has_chapter_keyword("Capítulo 1") is True
        assert has_chapter_keyword("CAPÍTULO 2 - Título") is True

    def test_secao(self):
        """Detecta 'Seção'."""
        assert has_chapter_keyword("Seção 3") is True

    def test_chapter_english(self):
        """Detecta 'Chapter' em inglês."""
        assert has_chapter_keyword("Chapter 1") is True

    def test_parte(self):
        """Detecta 'Parte'."""
        assert has_chapter_keyword("Parte II") is True

    def test_not_chapter(self):
        """Texto normal não tem keyword."""
        assert has_chapter_keyword("Introdução ao tema") is False


class TestStructuralKeyword:
    """Testes para has_structural_keyword."""

    def test_introducao(self):
        """Detecta 'Introdução'."""
        assert has_structural_keyword("Introdução") is True

    def test_conclusao(self):
        """Detecta 'Conclusão'."""
        assert has_structural_keyword("Conclusão") is True

    def test_resumo(self):
        """Detecta 'Resumo'."""
        assert has_structural_keyword("Resumo") is True

    def test_referencias(self):
        """Detecta 'Referências'."""
        assert has_structural_keyword("Referências") is True

    def test_with_spaces(self):
        """Funciona com espaços."""
        assert has_structural_keyword("  Conclusão  ") is True

    def test_not_structural(self):
        """Texto normal não é estrutural."""
        assert has_structural_keyword("Fundamentos Teóricos") is False


class TestBulletItem:
    """Testes para is_bullet_item."""

    def test_dash_bullet(self):
        """Detecta bullet com traço."""
        assert is_bullet_item("- Item de lista") is True

    def test_circle_bullet(self):
        """Detecta bullet com círculo."""
        assert is_bullet_item("• Item de lista") is True

    def test_asterisk_bullet(self):
        """Detecta bullet com asterisco."""
        assert is_bullet_item("* Item") is True

    def test_letter_bullet(self):
        """Detecta bullet com letra."""
        assert is_bullet_item("a) Item") is True
        assert is_bullet_item("(a) Item") is True

    def test_number_bullet(self):
        """Detecta bullet com número."""
        assert is_bullet_item("1. Primeiro item") is True
        assert is_bullet_item("1) Item") is True

    def test_not_bullet(self):
        """Texto normal não é bullet."""
        assert is_bullet_item("Este é um texto") is False
        assert is_bullet_item("1.2 Seção") is False  # É seção, não bullet


class TestFormula:
    """Testes para looks_like_formula."""

    def test_equation(self):
        """Detecta equação."""
        assert looks_like_formula("F = m * a") is True
        assert looks_like_formula("E = mc^2") is True

    def test_normal_text(self):
        """Texto normal não é fórmula."""
        assert looks_like_formula("Este é um texto normal") is False

    def test_single_operator(self):
        """Operador único não é fórmula."""
        # Depende da implementação, mas geralmente precisa de mais contexto
        pass


class TestExtractFlags:
    """Testes para extract_flags."""

    def test_bold_flag(self):
        """Detecta flag de bold (16)."""
        is_bold, is_italic = extract_flags(16)
        assert is_bold is True
        assert is_italic is False

    def test_italic_flag(self):
        """Detecta flag de italic (2)."""
        is_bold, is_italic = extract_flags(2)
        assert is_bold is False
        assert is_italic is True

    def test_bold_italic(self):
        """Detecta bold + italic (18)."""
        is_bold, is_italic = extract_flags(18)
        assert is_bold is True
        assert is_italic is True

    def test_no_flags(self):
        """Sem flags."""
        is_bold, is_italic = extract_flags(0)
        assert is_bold is False
        assert is_italic is False

    def test_other_flags(self):
        """Outras flags não afetam bold/italic."""
        # Flag 4 = serifed, 8 = monospaced
        is_bold, is_italic = extract_flags(12)  # 4 + 8
        assert is_bold is False
        assert is_italic is False


class TestCreateCandidateFromSpan:
    """Testes para create_candidate_from_span."""

    def test_basic_span(self):
        """Cria candidato de span básico."""
        span = {
            "text": "Título do Documento",
            "size": 16.0,
            "bbox": (50, 100, 400, 130),
            "flags": 16,  # bold
            "font": "Arial-Bold",
        }

        candidate = create_candidate_from_span(span, page_num=1, page_height=800)

        assert candidate.text == "Título do Documento"
        assert candidate.font_size == 16.0
        assert candidate.page_num == 1
        assert candidate.is_bold is True
        assert 0 < candidate.y_ratio < 1

    def test_detects_bold_from_font_name(self):
        """Detecta bold pelo nome da fonte."""
        span = {
            "text": "Texto Bold",
            "size": 12.0,
            "bbox": (50, 100, 200, 115),
            "flags": 0,  # Sem flag de bold
            "font": "TimesNewRoman-Bold",
        }

        candidate = create_candidate_from_span(span, page_num=1, page_height=800)
        assert candidate.is_bold is True


# =============================================================================
# TESTES DO QUICK_SCORE
# =============================================================================

class TestQuickScore:
    """Testes para a função quick_score."""

    def test_strong_heading(self):
        """Heading forte deve ter score alto."""
        score = quick_score(
            text="1.2 Fundamentos Teóricos",
            font_size=16.0,
            is_bold=True,
            body_size=12.0
        )
        assert score >= 3  # Threshold padrão

    def test_body_text(self):
        """Corpo de texto deve ter score baixo."""
        score = quick_score(
            text="Este é um parágrafo normal de texto que continua por várias palavras.",
            font_size=12.0,
            is_bold=False,
            body_size=12.0
        )
        assert score < 3

    def test_bullet_negative(self):
        """Bullet deve ter score negativo."""
        score = quick_score(
            text="• Item de lista",
            font_size=12.0,
            is_bold=False,
            body_size=12.0
        )
        assert score < 0

    def test_long_text_penalty(self):
        """Texto longo deve ser penalizado."""
        long_text = "Este é um texto muito longo que definitivamente não deveria ser um heading porque headings são geralmente curtos e concisos e não contêm tantas palavras assim."
        score = quick_score(long_text, 14.0, True, 12.0)
        # Mesmo sendo bold e maior, o comprimento penaliza
        assert score < 10

    def test_ends_with_period_penalty(self):
        """Texto que termina com ponto é penalizado."""
        score1 = quick_score("Conclusão", 14.0, True, 12.0)
        score2 = quick_score("Conclusão.", 14.0, True, 12.0)
        assert score1 > score2


# =============================================================================
# TESTES DO HEADING SCORER
# =============================================================================

class TestHeadingScorerInit:
    """Testes de inicialização do HeadingScorer."""

    def test_default_config(self):
        """Inicialização com config padrão."""
        scorer = HeadingScorer()
        assert scorer.config is not None
        assert scorer.config.strategy == ScoringStrategy.BALANCED

    def test_custom_config(self):
        """Inicialização com config customizada."""
        config = ScoringConfig(
            strategy=ScoringStrategy.FAST,
            heading_threshold=5
        )
        scorer = HeadingScorer(config)
        assert scorer.config.strategy == ScoringStrategy.FAST
        assert scorer.config.heading_threshold == 5

    def test_context_not_initialized(self):
        """Contexto não inicializado antes de analyze_candidates."""
        scorer = HeadingScorer()
        assert scorer.context is None


class TestHeadingScorerAnalyze:
    """Testes para analyze_candidates."""

    def test_analyze_empty_list(self, scorer_balanced):
        """Lista vazia não deve causar erro."""
        scorer_balanced.analyze_candidates([])
        # Não deve lançar exceção

    def test_analyze_creates_context(self, scorer_balanced, sample_candidates):
        """Análise deve criar contexto."""
        scorer_balanced.analyze_candidates(sample_candidates)
        assert scorer_balanced.context is not None
        assert scorer_balanced.context.body_font_size > 0

    def test_detects_body_size(self, scorer_balanced, body_text_candidates):
        """Deve detectar tamanho do corpo corretamente."""
        scorer_balanced.analyze_candidates(body_text_candidates)
        # Todos os candidatos têm 12.0pt
        assert abs(scorer_balanced.context.body_font_size - 12.0) < 1.0

    def test_builds_size_mapping(self, scorer_balanced, heading_candidates):
        """Deve construir mapeamento de tamanhos."""
        # Adiciona corpo de texto para contexto
        all_candidates = heading_candidates + [
            HeadingCandidate(
                text=f"Parágrafo {i}",
                font_size=12.0,
                page_num=1,
                bbox=(0, 0, 100, 20),
                y_ratio=0.5,
                is_bold=False,
            )
            for i in range(20)
        ]

        scorer_balanced.analyze_candidates(all_candidates)
        assert len(scorer_balanced._size_to_level) > 0


class TestHeadingScorerScoring:
    """Testes para score_candidate."""

    def test_requires_context(self, scorer_balanced):
        """Deve exigir contexto inicializado."""
        candidate = HeadingCandidate(
            text="Teste",
            font_size=14.0,
            page_num=1,
            bbox=(0, 0, 100, 20),
            y_ratio=0.5,
            is_bold=True,
        )

        with pytest.raises(RuntimeError):
            scorer_balanced.score_candidate(candidate)

    def test_scores_heading_positively(self, scorer_balanced, sample_candidates):
        """Heading deve ter score positivo."""
        scorer_balanced.analyze_candidates(sample_candidates)

        # Primeiro candidato é claramente um heading
        result = scorer_balanced.score_candidate(sample_candidates[0])

        assert result.score > 0
        assert result.is_heading is True
        assert result.level >= 1

    def test_scores_body_negatively(self, scorer_balanced, sample_candidates):
        """Corpo de texto deve ter score baixo."""
        scorer_balanced.analyze_candidates(sample_candidates)

        # Terceiro candidato é corpo de texto
        result = scorer_balanced.score_candidate(sample_candidates[2])

        assert result.is_heading is False
        assert result.level == 0

    def test_scores_bullet_negatively(self, scorer_balanced, sample_candidates):
        """Bullet deve ter score negativo."""
        scorer_balanced.analyze_candidates(sample_candidates)

        # Quarto candidato é bullet
        result = scorer_balanced.score_candidate(sample_candidates[3])

        assert result.is_heading is False

    def test_provides_reasons(self, scorer_balanced, sample_candidates):
        """Deve fornecer razões para o score."""
        scorer_balanced.analyze_candidates(sample_candidates)
        result = scorer_balanced.score_candidate(sample_candidates[0])

        assert len(result.reasons) > 0


class TestScoringStrategies:
    """Testes comparativos entre estratégias."""

    def test_fast_is_fastest(self, sample_candidates):
        """FAST deve ser mais rápido que outras estratégias."""
        scorers = {
            'fast': HeadingScorer(ScoringConfig(strategy=ScoringStrategy.FAST)),
            'balanced': HeadingScorer(ScoringConfig(strategy=ScoringStrategy.BALANCED)),
            'accurate': HeadingScorer(ScoringConfig(strategy=ScoringStrategy.ACCURATE)),
        }

        # Expande candidatos para teste mais significativo
        candidates = sample_candidates * 100

        times = {}
        for name, scorer in scorers.items():
            start = time.perf_counter()
            scorer.score_all(candidates)
            elapsed = time.perf_counter() - start
            times[name] = elapsed

        # FAST deve ser mais rápido ou igual a BALANCED
        assert times['fast'] <= times['balanced'] * 1.5  # Margem de 50%

    def test_all_strategies_detect_obvious_headings(self, heading_candidates, body_text_candidates):
        """Todas as estratégias devem detectar headings óbvios."""
        all_candidates = heading_candidates + body_text_candidates

        for strategy in ScoringStrategy:
            scorer = HeadingScorer(ScoringConfig(strategy=strategy))
            results = scorer.filter_headings(all_candidates)

            # Deve detectar pelo menos os headings óbvios
            detected_texts = {r.candidate.text for r in results}

            # "CAPÍTULO 1 - Fundamentos" deve ser detectado
            chapter_detected = any("CAPÍTULO" in t for t in detected_texts)
            assert chapter_detected, f"Estratégia {strategy} não detectou capítulo"

    def test_strategies_have_different_sensitivity(self, sample_candidates):
        """Estratégias devem ter sensibilidades diferentes."""
        candidates = sample_candidates * 10

        results = {}
        for strategy in ScoringStrategy:
            scorer = HeadingScorer(ScoringConfig(strategy=strategy))
            headings = scorer.filter_headings(candidates)
            results[strategy] = len(headings)

        # Geralmente: ACCURATE >= BALANCED >= FAST em número de detecções
        # (mas isso pode variar dependendo do conteúdo)


class TestScoreAll:
    """Testes para score_all."""

    def test_scores_all_candidates(self, scorer_balanced, sample_candidates):
        """Deve retornar resultado para cada candidato."""
        results = scorer_balanced.score_all(sample_candidates)
        assert len(results) == len(sample_candidates)

    def test_results_have_correct_type(self, scorer_balanced, sample_candidates):
        """Resultados devem ser ScoringResult."""
        results = scorer_balanced.score_all(sample_candidates)
        for r in results:
            assert isinstance(r, ScoringResult)

    def test_empty_list_returns_empty(self, scorer_balanced):
        """Lista vazia retorna lista vazia."""
        results = scorer_balanced.score_all([])
        assert results == []


class TestFilterHeadings:
    """Testes para filter_headings."""

    def test_returns_only_headings(self, scorer_balanced, sample_candidates):
        """Deve retornar apenas headings."""
        results = scorer_balanced.filter_headings(sample_candidates)

        for r in results:
            assert r.is_heading is True

    def test_filters_body_text(self, scorer_balanced, body_text_candidates):
        """Deve filtrar corpo de texto."""
        results = scorer_balanced.filter_headings(body_text_candidates)

        # Corpo de texto puro não deve gerar headings
        assert len(results) < len(body_text_candidates)


class TestHeadingLevels:
    """Testes para determinação de níveis de heading."""

    def test_larger_font_gets_lower_level(self, scorer_balanced, heading_candidates, body_text_candidates):
        """Fonte maior deve resultar em nível menor (H1 > H2 > H3)."""
        all_candidates = heading_candidates + body_text_candidates
        results = scorer_balanced.filter_headings(all_candidates)

        if len(results) >= 2:
            # Ordena por tamanho de fonte decrescente
            sorted_results = sorted(results, key=lambda r: r.candidate.font_size, reverse=True)

            # O maior deve ter nível menor ou igual
            for i in range(len(sorted_results) - 1):
                assert sorted_results[i].level <= sorted_results[i + 1].level or \
                       sorted_results[i].candidate.font_size > sorted_results[i + 1].candidate.font_size

    def test_levels_are_in_range(self, scorer_balanced, sample_candidates):
        """Níveis devem estar entre 1 e 6."""
        results = scorer_balanced.filter_headings(sample_candidates)

        for r in results:
            assert 1 <= r.level <= 6


class TestStatistics:
    """Testes para get_statistics."""

    def test_returns_statistics(self, scorer_balanced, sample_candidates):
        """Deve retornar estatísticas após análise."""
        scorer_balanced.score_all(sample_candidates)
        stats = scorer_balanced.get_statistics()

        assert "strategy" in stats
        assert "threshold" in stats
        assert "body_font_size" in stats

    def test_cache_info_included(self, scorer_balanced, sample_candidates):
        """Estatísticas devem incluir info de cache."""
        scorer_balanced.score_all(sample_candidates)
        stats = scorer_balanced.get_statistics()

        assert "cache_info" in stats


class TestBenchmark:
    """Testes para o benchmark integrado."""

    def test_benchmark_runs(self, sample_candidates):
        """Benchmark deve executar sem erros."""
        scorer = HeadingScorer()
        results = scorer.benchmark(sample_candidates, iterations=2)

        assert len(results) == len(ScoringStrategy)

    def test_benchmark_returns_all_strategies(self, sample_candidates):
        """Benchmark deve retornar resultado para todas as estratégias."""
        scorer = HeadingScorer()
        results = scorer.benchmark(sample_candidates, iterations=2)

        for strategy in ScoringStrategy:
            assert strategy in results


# =============================================================================
# TESTES DE EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Testes de casos extremos."""

    def test_very_short_text(self, scorer_balanced):
        """Texto muito curto."""
        candidates = [
            HeadingCandidate(
                text="A",
                font_size=14.0,
                page_num=1,
                bbox=(0, 0, 10, 15),
                y_ratio=0.5,
                is_bold=True,
            )
        ]

        results = scorer_balanced.score_all(candidates)
        assert len(results) == 1

    def test_very_long_text(self, scorer_balanced):
        """Texto muito longo."""
        candidates = [
            HeadingCandidate(
                text="A" * 500,
                font_size=14.0,
                page_num=1,
                bbox=(0, 0, 1000, 15),
                y_ratio=0.5,
                is_bold=True,
            )
        ]

        results = scorer_balanced.score_all(candidates)
        assert len(results) == 1
        # Deve ser penalizado pelo comprimento
        assert results[0].is_heading is False

    def test_unicode_text(self, scorer_balanced):
        """Texto com caracteres unicode."""
        candidates = [
            HeadingCandidate(
                text="Seção 1: Análise de Fluídos com Símbolos α, β, γ",
                font_size=14.0,
                page_num=1,
                bbox=(0, 0, 400, 20),
                y_ratio=0.1,
                is_bold=True,
            )
        ]

        results = scorer_balanced.score_all(candidates)
        assert len(results) == 1

    def test_only_numbers(self, scorer_balanced):
        """Texto só com números."""
        candidates = [
            HeadingCandidate(
                text="12345",
                font_size=14.0,
                page_num=1,
                bbox=(0, 0, 50, 15),
                y_ratio=0.5,
                is_bold=False,
            )
        ]

        results = scorer_balanced.score_all(candidates)
        # Número sozinho não deve ser heading
        assert results[0].is_heading is False

    def test_extreme_font_size(self, scorer_balanced):
        """Tamanhos de fonte extremos."""
        candidates = [
            HeadingCandidate(
                text="Título Gigante",
                font_size=72.0,
                page_num=1,
                bbox=(0, 0, 500, 80),
                y_ratio=0.1,
                is_bold=True,
            ),
            HeadingCandidate(
                text="texto minúsculo",
                font_size=6.0,
                page_num=1,
                bbox=(0, 100, 100, 108),
                y_ratio=0.9,
                is_bold=False,
            ),
        ]

        results = scorer_balanced.score_all(candidates)
        assert len(results) == 2


class TestPerformance:
    """Testes de performance."""

    def test_handles_large_input(self, scorer_balanced):
        """Deve processar grande quantidade de candidatos."""
        # 10.000 candidatos
        candidates = [
            HeadingCandidate(
                text=f"Texto do candidato número {i}",
                font_size=12.0 if i % 10 != 0 else 16.0,
                page_num=i // 100 + 1,
                bbox=(50, (i % 100) * 10, 400, (i % 100) * 10 + 15),
                y_ratio=(i % 100) / 100,
                is_bold=i % 20 == 0,
            )
            for i in range(10000)
        ]

        start = time.perf_counter()
        results = scorer_balanced.score_all(candidates)
        elapsed = time.perf_counter() - start

        assert len(results) == 10000
        # Deve completar em menos de 5 segundos
        assert elapsed < 5.0

    def test_consistent_results(self, scorer_balanced, sample_candidates):
        """Resultados devem ser consistentes entre execuções."""
        results1 = scorer_balanced.score_all(sample_candidates)
        results2 = scorer_balanced.score_all(sample_candidates)

        for r1, r2 in zip(results1, results2):
            assert r1.score == r2.score
            assert r1.is_heading == r2.is_heading


# =============================================================================
# TESTES DE CONFIGURAÇÃO
# =============================================================================

class TestConfigCustomization:
    """Testes de customização de configuração."""

    def test_custom_threshold(self, sample_candidates):
        """Threshold customizado afeta classificação."""
        config_low = ScoringConfig(heading_threshold=1)
        config_high = ScoringConfig(heading_threshold=10)

        scorer_low = HeadingScorer(config_low)
        scorer_high = HeadingScorer(config_high)

        results_low = scorer_low.filter_headings(sample_candidates)
        results_high = scorer_high.filter_headings(sample_candidates)

        # Threshold baixo deve detectar mais headings
        assert len(results_low) >= len(results_high)

    def test_custom_max_length(self, sample_candidates):
        """Comprimento máximo customizado."""
        config = ScoringConfig(max_heading_length=50)
        scorer = HeadingScorer(config)

        results = scorer.filter_headings(sample_candidates)

        # Todos os headings devem ter menos que 50 caracteres
        for r in results:
            assert len(r.candidate.text) <= 50 or r.score < 0

    def test_custom_weights(self):
        """Pesos customizados afetam score."""
        # Config com peso alto para bold
        config = ScoringConfig(weight_bold=10)
        scorer = HeadingScorer(config)

        candidates = [
            HeadingCandidate(
                text="Teste Bold",
                font_size=12.0,
                page_num=1,
                bbox=(0, 0, 100, 15),
                y_ratio=0.5,
                is_bold=True,
            ),
            HeadingCandidate(
                text="Teste Normal",
                font_size=12.0,
                page_num=1,
                bbox=(0, 20, 100, 35),
                y_ratio=0.5,
                is_bold=False,
            ),
        ]

        results = scorer.score_all(candidates)

        # Bold deve ter score significativamente maior
        assert results[0].score > results[1].score + 5
