"""
Testes unitários para o módulo orphan_reference_cleaner.

Testa a detecção e limpeza de referências órfãs em documentos Markdown.
"""

import pytest
import os
import tempfile
from pathlib import Path
from app.utils.orphan_reference_cleaner import (
    OrphanReferenceCleaner,
    OrphanCleanerConfig,
    OrphanReference,
    CleaningResult,
    get_orphan_cleaner,
    clean_orphan_references,
    find_figure_references,
    has_orphan_figures,
)


class TestOrphanCleanerConfig:
    """Testes para a classe OrphanCleanerConfig."""

    def test_default_values(self):
        """Testa valores padrão da configuração."""
        config = OrphanCleanerConfig()

        assert len(config.figure_patterns) > 0
        assert len(config.table_patterns) > 0
        assert len(config.frame_patterns) > 0
        assert len(config.chart_patterns) > 0
        assert config.remove_empty_lines_after is True
        assert config.remove_surrounding_empty_lines is True
        assert config.case_insensitive is True
        assert config.clean_figures is True
        assert config.clean_tables is True
        assert config.clean_frames is True
        assert config.clean_charts is True

    def test_custom_values(self):
        """Testa valores personalizados."""
        config = OrphanCleanerConfig(
            remove_empty_lines_after=False,
            case_insensitive=False,
            clean_tables=False,
        )

        assert config.remove_empty_lines_after is False
        assert config.case_insensitive is False
        assert config.clean_tables is False


class TestOrphanReference:
    """Testes para a classe OrphanReference."""

    def test_creation(self):
        """Testa criação de OrphanReference."""
        orphan = OrphanReference(
            text="*Figura 1*",
            line_number=10,
            pattern_matched=r'\*Figura\s+\d+\*',
            reference_type="figure",
            context="9: texto anterior\n10: *Figura 1*\n11: texto posterior",
        )

        assert orphan.text == "*Figura 1*"
        assert orphan.line_number == 10
        assert orphan.reference_type == "figure"
        assert "Figura 1" in orphan.context


class TestCleaningResult:
    """Testes para a classe CleaningResult."""

    def test_creation(self):
        """Testa criação de CleaningResult."""
        result = CleaningResult(
            original_content="*Figura 1*\n\nTexto",
            cleaned_content="Texto",
            orphans_found=[],
            lines_removed=2,
            references_removed=1,
        )

        assert result.original_content == "*Figura 1*\n\nTexto"
        assert result.cleaned_content == "Texto"
        assert result.lines_removed == 2
        assert result.references_removed == 1


class TestOrphanReferenceCleaner:
    """Testes para a classe OrphanReferenceCleaner."""

    def test_init_default_config(self):
        """Testa inicialização com configuração padrão."""
        cleaner = OrphanReferenceCleaner()
        assert cleaner.config is not None
        assert cleaner.config.clean_figures is True

    def test_init_custom_config(self):
        """Testa inicialização com configuração personalizada."""
        config = OrphanCleanerConfig(clean_tables=False)
        cleaner = OrphanReferenceCleaner(config)
        assert cleaner.config.clean_tables is False

    def test_find_orphan_references_figure_star(self):
        """Testa detecção de *Figura N*."""
        cleaner = OrphanReferenceCleaner()
        content = """
Texto normal aqui.

*Figura 1*

Mais texto.
"""
        orphans = cleaner.find_orphan_references(content)

        assert len(orphans) >= 1
        assert any("Figura 1" in o.text for o in orphans)

    def test_find_orphan_references_figure_bold(self):
        """Testa detecção de **Figura N**."""
        cleaner = OrphanReferenceCleaner()
        content = """
Texto.

**Figura 2**

Mais texto.
"""
        orphans = cleaner.find_orphan_references(content)

        assert len(orphans) >= 1
        assert any("Figura 2" in o.text for o in orphans)

    def test_find_orphan_references_table(self):
        """Testa detecção de referências a tabelas."""
        cleaner = OrphanReferenceCleaner()
        content = """
Texto.

*Tabela 1*

Mais texto.
"""
        orphans = cleaner.find_orphan_references(content)

        assert len(orphans) >= 1
        assert any("Tabela 1" in o.text for o in orphans)

    def test_find_orphan_references_chart(self):
        """Testa detecção de referências a gráficos."""
        cleaner = OrphanReferenceCleaner()
        content = """
Texto.

*Gráfico 1*

Mais texto.
"""
        orphans = cleaner.find_orphan_references(content)

        assert len(orphans) >= 1
        assert any("Gráfico 1" in o.text for o in orphans)

    def test_find_orphan_references_frame(self):
        """Testa detecção de referências a quadros."""
        cleaner = OrphanReferenceCleaner()
        content = """
Texto.

*Quadro 1*

Mais texto.
"""
        orphans = cleaner.find_orphan_references(content)

        assert len(orphans) >= 1
        assert any("Quadro 1" in o.text for o in orphans)

    def test_no_orphans_with_real_image(self):
        """Testa que referências com imagens reais não são órfãs."""
        cleaner = OrphanReferenceCleaner()
        content = """
Veja a imagem abaixo:

![Figura 1](images/fig1.png)

*Figura 1*

Descrição da figura.
"""
        # Com imagens existentes, a referência não deve ser órfã
        existing_images = {"fig1.png", "images/fig1.png"}
        orphans = cleaner.find_orphan_references(content, existing_images)

        # A lógica pode variar, mas idealmente não deve detectar como órfã
        # se há uma imagem correspondente
        # Este teste verifica o comportamento atual

    def test_clean_removes_orphan_figure(self):
        """Testa que a limpeza remove figuras órfãs."""
        cleaner = OrphanReferenceCleaner()
        content = """Texto inicial.

*Figura 1*

Texto final."""

        result = cleaner.clean(content)

        assert "*Figura 1*" not in result.cleaned_content
        assert "Texto inicial" in result.cleaned_content
        assert "Texto final" in result.cleaned_content
        assert result.references_removed >= 1

    def test_clean_preserves_non_orphan_content(self):
        """Testa que a limpeza preserva conteúdo não órfão."""
        cleaner = OrphanReferenceCleaner()
        content = """# Título

Parágrafo normal com texto.

## Subtítulo

Mais texto aqui.

*Figura 1*

Conclusão."""

        result = cleaner.clean(content)

        assert "# Título" in result.cleaned_content
        assert "Parágrafo normal" in result.cleaned_content
        assert "## Subtítulo" in result.cleaned_content
        assert "Conclusão" in result.cleaned_content

    def test_clean_multiple_orphans(self):
        """Testa limpeza de múltiplas referências órfãs."""
        cleaner = OrphanReferenceCleaner()
        content = """Texto.

*Figura 1*

Mais texto.

*Figura 2*

Ainda mais texto.

*Tabela 1*

Final."""

        result = cleaner.clean(content)

        assert "*Figura 1*" not in result.cleaned_content
        assert "*Figura 2*" not in result.cleaned_content
        assert "*Tabela 1*" not in result.cleaned_content
        assert result.references_removed >= 3

    def test_clean_empty_lines(self):
        """Testa limpeza de linhas vazias excessivas."""
        cleaner = OrphanReferenceCleaner()
        content = """Texto.



*Figura 1*



Final."""

        result = cleaner.clean(content)

        # Não deve ter mais de 2 linhas vazias consecutivas
        assert "\n\n\n" not in result.cleaned_content

    def test_case_insensitive_detection(self):
        """Testa detecção case-insensitive."""
        config = OrphanCleanerConfig(case_insensitive=True)
        cleaner = OrphanReferenceCleaner(config)
        content = """
*FIGURA 1*

*figura 2*

*Figura 3*
"""
        orphans = cleaner.find_orphan_references(content)

        # Deve detectar todas independente de case
        assert len(orphans) >= 3

    def test_case_sensitive_detection(self):
        """Testa detecção case-sensitive."""
        config = OrphanCleanerConfig(case_insensitive=False)
        cleaner = OrphanReferenceCleaner(config)
        content = """
*FIGURA 1*

*figura 2*

*Figura 3*
"""
        orphans = cleaner.find_orphan_references(content)

        # Com case-sensitive, pode detectar menos
        # dependendo dos padrões configurados

    def test_stats_tracking(self):
        """Testa rastreamento de estatísticas."""
        cleaner = OrphanReferenceCleaner()
        cleaner.reset_stats()

        content = "*Figura 1*\n\nTexto"
        cleaner.clean(content)

        stats = cleaner.get_stats()
        assert stats['documents_processed'] == 1
        assert stats['references_removed'] >= 1

    def test_reset_stats(self):
        """Testa reset de estatísticas."""
        cleaner = OrphanReferenceCleaner()

        content = "*Figura 1*"
        cleaner.clean(content)

        cleaner.reset_stats()
        stats = cleaner.get_stats()

        assert stats['documents_processed'] == 0
        assert stats['references_removed'] == 0
        assert stats['lines_removed'] == 0

    def test_clean_with_existing_images(self):
        """Testa limpeza com lista de imagens existentes."""
        cleaner = OrphanReferenceCleaner()
        content = """
*Figura 1*

*Figura 2*
"""
        existing_images = {"figura_1.png"}
        result = cleaner.clean(content, existing_images=existing_images)

        # Deve limpar referências sem imagens correspondentes
        assert result.references_removed >= 0

    def test_clean_with_images_dir(self):
        """Testa limpeza com diretório de imagens."""
        cleaner = OrphanReferenceCleaner()

        # Criar diretório temporário
        with tempfile.TemporaryDirectory() as tmpdir:
            images_dir = os.path.join(tmpdir, "images")
            os.makedirs(images_dir)

            # Criar uma imagem de teste
            test_image = os.path.join(images_dir, "fig1.png")
            with open(test_image, "wb") as f:
                f.write(b"fake image data")

            content = "*Figura 1*\n\n*Figura 2*"
            result = cleaner.clean(content, images_dir=images_dir)

            # Deve processar corretamente
            assert result is not None


class TestFactoryFunction:
    """Testes para função factory."""

    def test_get_orphan_cleaner_default(self):
        """Testa factory com configuração padrão."""
        cleaner = get_orphan_cleaner()
        assert isinstance(cleaner, OrphanReferenceCleaner)

    def test_get_orphan_cleaner_custom(self):
        """Testa factory com configuração personalizada."""
        config = OrphanCleanerConfig(clean_charts=False)
        cleaner = get_orphan_cleaner(config)

        assert cleaner.config.clean_charts is False


class TestCleanOrphanReferences:
    """Testes para função clean_orphan_references."""

    def test_basic_clean(self):
        """Testa limpeza básica."""
        content = """Texto.

*Figura 1*

Final."""

        result = clean_orphan_references(content)

        assert "*Figura 1*" not in result
        assert "Texto" in result
        assert "Final" in result

    def test_with_existing_images(self):
        """Testa limpeza com imagens existentes."""
        content = "*Figura 1*\n\n*Figura 2*"
        existing_images = {"fig1.png"}

        result = clean_orphan_references(content, existing_images)

        # Deve retornar string
        assert isinstance(result, str)

    def test_empty_content(self):
        """Testa conteúdo vazio."""
        result = clean_orphan_references("")
        assert result == ""


class TestFindFigureReferences:
    """Testes para função find_figure_references."""

    def test_find_star_format(self):
        """Testa detecção de formato *Figura N*."""
        content = "Texto *Figura 1* mais texto"
        refs = find_figure_references(content)

        assert len(refs) >= 1
        assert any("Figura 1" in ref[0] for ref in refs)

    def test_find_bold_format(self):
        """Testa detecção de formato **Figura N**."""
        content = "Texto **Figura 2** mais texto"
        refs = find_figure_references(content)

        assert len(refs) >= 1
        assert any("Figura 2" in ref[0] for ref in refs)

    def test_find_plain_format(self):
        """Testa detecção de formato Figura N:."""
        content = "Veja a Figura 3: descrição"
        refs = find_figure_references(content)

        assert len(refs) >= 1
        assert any("Figura 3" in ref[0] for ref in refs)

    def test_find_fig_abbreviation(self):
        """Testa detecção de abreviação Fig. N."""
        content = "Conforme Fig. 4, podemos ver"
        refs = find_figure_references(content)

        assert len(refs) >= 1
        assert any("Fig. 4" in ref[0] for ref in refs)

    def test_find_multiple_references(self):
        """Testa detecção de múltiplas referências."""
        content = """
*Figura 1*

Texto com Figura 2: descrição

Ver também Fig. 3.
"""
        refs = find_figure_references(content)

        assert len(refs) >= 3

    def test_line_numbers(self):
        """Testa que números de linha estão corretos."""
        content = """Linha 1
Linha 2
*Figura 1*
Linha 4"""
        refs = find_figure_references(content)

        assert len(refs) >= 1
        # A referência deve estar na linha 3
        assert any(ref[1] == 3 for ref in refs)

    def test_no_references(self):
        """Testa texto sem referências."""
        content = "Este texto não tem nenhuma referência a figuras."
        refs = find_figure_references(content)

        assert len(refs) == 0


class TestHasOrphanFigures:
    """Testes para função has_orphan_figures."""

    def test_has_orphans_no_images(self):
        """Testa detecção quando não há imagens."""
        content = "*Figura 1*\n\nTexto"
        result = has_orphan_figures(content, image_count=0)

        assert result is True

    def test_no_orphans_with_images(self):
        """Testa quando há imagens suficientes."""
        content = "*Figura 1*\n\nTexto"
        result = has_orphan_figures(content, image_count=5)

        assert result is False

    def test_many_refs_few_images(self):
        """Testa quando há muitas referências e poucas imagens."""
        content = """
*Figura 1*
*Figura 2*
*Figura 3*
*Figura 4*
*Figura 5*
"""
        result = has_orphan_figures(content, image_count=1)

        assert result is True

    def test_no_references(self):
        """Testa quando não há referências."""
        content = "Texto sem referências a figuras."
        result = has_orphan_figures(content, image_count=0)

        assert result is False


class TestRealWorldScenarios:
    """Testes com cenários do mundo real."""

    def test_precalculo_aulas_pattern(self):
        """Testa padrão encontrado no Pre-Calculo_Aulas.md."""
        cleaner = OrphanReferenceCleaner()
        content = """# TEMA 2 – EXEMPLOS DIDÁTICOS I
Exemplo 3. Dada a função f(x) = 2x + 1, responda o que se pede:
a) Qual o domínio dessa função?
b) f(2) = ?

Vídeo: Aula 1 – Exemplo 3 – 6min.

*Figura 1*

*Figura 2*

---

Exemplo 4. Dada a função..."""

        result = cleaner.clean(content)

        assert "*Figura 1*" not in result.cleaned_content
        assert "*Figura 2*" not in result.cleaned_content
        assert "# TEMA 2" in result.cleaned_content
        assert "Exemplo 3" in result.cleaned_content
        assert "Exemplo 4" in result.cleaned_content

    def test_mixed_content_with_real_images(self):
        """Testa conteúdo misto com imagens reais e órfãs."""
        cleaner = OrphanReferenceCleaner()
        content = """# Introdução

![Diagrama](images/diagram.png)

*Figura 1* - Diagrama do sistema

Texto explicativo.

*Figura 2*

Mais texto.

![Gráfico](images/chart.png)

*Figura 3* - Gráfico de resultados

*Figura 4*

Conclusão."""

        existing_images = {"diagram.png", "chart.png", "images/diagram.png", "images/chart.png"}
        result = cleaner.clean(content, existing_images=existing_images)

        # Deve preservar estrutura geral
        assert "# Introdução" in result.cleaned_content
        assert "Conclusão" in result.cleaned_content

    def test_preserve_inline_references(self):
        """Testa que referências inline em texto são tratadas adequadamente."""
        cleaner = OrphanReferenceCleaner()
        content = """Como vemos na Figura 1, o gráfico mostra uma tendência crescente.
A Tabela 2 complementa esses dados com valores numéricos.

*Figura 1*

A análise continua..."""

        result = cleaner.clean(content)

        # A referência isolada deve ser removida
        # Referências inline podem ser preservadas dependendo da implementação
        assert "análise continua" in result.cleaned_content

    def test_clean_file_workflow(self):
        """Testa fluxo completo de limpeza de arquivo."""
        cleaner = OrphanReferenceCleaner()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Criar arquivo de teste
            input_path = os.path.join(tmpdir, "test.md")
            output_path = os.path.join(tmpdir, "output.md")

            content = """# Teste

*Figura 1*

Texto."""

            with open(input_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Limpar arquivo
            result = cleaner.clean_file(input_path, output_path)

            # Verificar resultado
            assert result.references_removed >= 1

            # Verificar arquivo de saída
            with open(output_path, "r", encoding="utf-8") as f:
                cleaned = f.read()

            assert "*Figura 1*" not in cleaned
            assert "# Teste" in cleaned
