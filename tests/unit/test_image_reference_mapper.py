import pytest
from app.utils.image_reference_mapper import ImageReference, ImageReferenceMapper


class TestImageReference:
    """Testes para a dataclass ImageReference"""

    def test_image_reference_creation(self):
        """Deve criar uma referência de imagem"""
        ref = ImageReference(
            ref_type="figura",
            ref_number=1,
            position=10,
            text_snippet="Ver figura 1 para mais detalhes"
        )
        assert ref.ref_type == "figura"
        assert ref.ref_number == 1
        assert ref.position == 10
        assert ref.text_snippet == "Ver figura 1 para mais detalhes"

    def test_image_reference_different_types(self):
        """Deve suportar diferentes tipos de referências"""
        types = ["figura", "tabela", "imagem", "gráfico", "figure", "table"]
        for ref_type in types:
            ref = ImageReference(
                ref_type=ref_type,
                ref_number=1,
                position=0,
                text_snippet="test"
            )
            assert ref.ref_type == ref_type


class TestImageReferenceMapperInit:
    """Testes para inicialização do ImageReferenceMapper"""

    def test_mapper_init(self):
        """Deve inicializar corretamente"""
        mapper = ImageReferenceMapper()
        assert mapper.references == []
        assert mapper.image_map == {}
        assert mapper.page_images == {}

    def test_mapper_creates_instances(self):
        """Deve criar instâncias independentes"""
        mapper1 = ImageReferenceMapper()
        mapper2 = ImageReferenceMapper()
        mapper1.add_image(1, "image1.png")
        assert 1 not in mapper2.page_images


class TestAddImage:
    """Testes para adicionar imagens ao mapeador"""

    def test_add_single_image(self):
        """Deve adicionar uma única imagem"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/page1_img1.png")
        assert 1 in mapper.page_images
        assert "images/page1_img1.png" in mapper.page_images[1]

    def test_add_multiple_images_same_page(self):
        """Deve adicionar múltiplas imagens da mesma página"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/page1_img1.png")
        mapper.add_image(1, "images/page1_img2.png")
        mapper.add_image(1, "images/page1_img3.png")
        assert len(mapper.page_images[1]) == 3

    def test_add_images_different_pages(self):
        """Deve adicionar imagens de páginas diferentes"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/page1_img1.png")
        mapper.add_image(2, "images/page2_img1.png")
        mapper.add_image(3, "images/page3_img1.png")
        assert len(mapper.page_images) == 3
        assert len(mapper.page_images[1]) == 1
        assert len(mapper.page_images[2]) == 1
        assert len(mapper.page_images[3]) == 1


class TestFindReferencesInText:
    """Testes para encontrar referências no texto"""

    def test_find_figura_reference(self):
        """Deve encontrar referência 'figura'"""
        mapper = ImageReferenceMapper()
        text = "Como visto na figura 1, podemos observar..."
        refs = mapper.find_references_in_text(text)
        assert len(refs) == 1
        assert refs[0].ref_type == "figura"
        assert refs[0].ref_number == 1

    def test_find_tabela_reference(self):
        """Deve encontrar referência 'tabela'"""
        mapper = ImageReferenceMapper()
        text = "Conforme apresentado na tabela 2, temos..."
        refs = mapper.find_references_in_text(text)
        assert len(refs) == 1
        assert refs[0].ref_type == "tabela"
        assert refs[0].ref_number == 2

    def test_find_imagem_reference(self):
        """Deve encontrar referência 'imagem'"""
        mapper = ImageReferenceMapper()
        text = "A imagem 3 mostra o resultado..."
        refs = mapper.find_references_in_text(text)
        assert len(refs) == 1
        assert refs[0].ref_type == "imagem"
        assert refs[0].ref_number == 3

    def test_find_grafico_reference(self):
        """Deve encontrar referência 'gráfico'"""
        mapper = ImageReferenceMapper()
        text = "No gráfico 4 é possível ver..."
        refs = mapper.find_references_in_text(text)
        assert len(refs) == 1
        assert refs[0].ref_type == "gráfico"
        assert refs[0].ref_number == 4

    def test_find_fig_abbreviated(self):
        """Deve encontrar 'fig.' abreviado"""
        mapper = ImageReferenceMapper()
        text = "Ver fig. 5 para detalhes"
        refs = mapper.find_references_in_text(text)
        assert len(refs) >= 1
        assert any(r.ref_number == 5 for r in refs)

    def test_find_english_references(self):
        """Deve encontrar referências em inglês"""
        mapper = ImageReferenceMapper()
        text = "As shown in figure 1, and in table 2"
        refs = mapper.find_references_in_text(text)
        assert len(refs) >= 2

    def test_find_multiple_references_same_text(self):
        """Deve encontrar múltiplas referências no mesmo texto"""
        mapper = ImageReferenceMapper()
        text = "Figura 1 mostra X. Tabela 2 mostra Y. Figura 3 mostra Z."
        refs = mapper.find_references_in_text(text)
        assert len(refs) == 3

    def test_find_references_case_insensitive(self):
        """Deve encontrar referências case-insensitively"""
        mapper = ImageReferenceMapper()
        text = "FIGURA 1 e Figura 2 e figura 3"
        refs = mapper.find_references_in_text(text)
        assert len(refs) >= 3

    def test_find_references_no_match(self):
        """Deve retornar lista vazia quando não há referências"""
        mapper = ImageReferenceMapper()
        text = "Este é um texto comum sem referências de imagens"
        refs = mapper.find_references_in_text(text)
        assert len(refs) == 0

    def test_find_references_adds_to_mapper(self):
        """Deve adicionar referências ao mapeador"""
        mapper = ImageReferenceMapper()
        assert len(mapper.references) == 0
        mapper.find_references_in_text("Figura 1 é interessante")
        assert len(mapper.references) > 0

    def test_reference_contains_snippet(self):
        """Deve extrair snippet de contexto da referência"""
        mapper = ImageReferenceMapper()
        text = "Algum texto antes da figura 1. Mais texto depois."
        refs = mapper.find_references_in_text(text)
        assert len(refs) > 0
        assert refs[0].text_snippet != ""
        assert "figura" in refs[0].text_snippet.lower()

    def test_find_references_with_page_num(self):
        """Deve aceitar número de página como parâmetro"""
        mapper = ImageReferenceMapper()
        text = "Figura 1 está nesta página"
        refs = mapper.find_references_in_text(text, page_num=5)
        assert len(refs) > 0


class TestMapImageToReference:
    """Testes para mapear imagens a referências"""

    def test_map_single_reference(self):
        """Deve mapear uma imagem a uma referência"""
        mapper = ImageReferenceMapper()
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")
        assert ("figura", 1) in mapper.image_map
        assert mapper.image_map[("figura", 1)] == "images/fig1.png"

    def test_map_multiple_references(self):
        """Deve mapear múltiplas imagens"""
        mapper = ImageReferenceMapper()
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")
        mapper.map_image_to_reference("figura", 2, "images/fig2.png")
        mapper.map_image_to_reference("tabela", 1, "images/tab1.png")
        assert len(mapper.image_map) == 3

    def test_map_reference_case_insensitive(self):
        """Deve ser case-insensitive ao mapear"""
        mapper = ImageReferenceMapper()
        mapper.map_image_to_reference("FIGURA", 1, "images/fig1.png")
        mapper.map_image_to_reference("Figura", 1, "images/fig2.png")
        # A segunda deve sobrescrever a primeira
        assert mapper.image_map[("figura", 1)] == "images/fig2.png"

    def test_map_overwrite_reference(self):
        """Deve permitir sobrescrever um mapeamento"""
        mapper = ImageReferenceMapper()
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")
        mapper.map_image_to_reference("figura", 1, "images/fig1_new.png")
        assert mapper.image_map[("figura", 1)] == "images/fig1_new.png"


class TestGetImageForReference:
    """Testes para obter imagem de uma referência"""

    def test_get_mapped_image(self):
        """Deve retornar imagem mapeada"""
        mapper = ImageReferenceMapper()
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")
        image = mapper.get_image_for_reference("figura", 1)
        assert image == "images/fig1.png"

    def test_get_unmapped_image(self):
        """Deve retornar None para imagem não mapeada"""
        mapper = ImageReferenceMapper()
        image = mapper.get_image_for_reference("figura", 999)
        assert image is None

    def test_get_image_case_insensitive(self):
        """Deve ser case-insensitive ao recuperar"""
        mapper = ImageReferenceMapper()
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")
        image = mapper.get_image_for_reference("FIGURA", 1)
        assert image == "images/fig1.png"


class TestGetNextAvailableImage:
    """Testes para obter próxima imagem disponível"""

    def test_get_next_image_single(self):
        """Deve retornar primeira imagem disponível"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/page1_img1.png")
        image = mapper.get_next_available_image(1)
        assert image == "images/page1_img1.png"

    def test_get_next_image_multiple(self):
        """Deve retornar primeira imagem não mapeada"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/page1_img1.png")
        mapper.add_image(1, "images/page1_img2.png")
        mapper.add_image(1, "images/page1_img3.png")

        # Mapear primeira
        mapper.map_image_to_reference("figura", 1, "images/page1_img1.png")

        # Próxima disponível deve ser a segunda
        image = mapper.get_next_available_image(1, exclude_used=True)
        assert image == "images/page1_img2.png"

    def test_get_next_image_exclude_used_false(self):
        """Deve retornar primeira imagem quando exclude_used=False"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/page1_img1.png")
        mapper.add_image(1, "images/page1_img2.png")
        mapper.map_image_to_reference("figura", 1, "images/page1_img1.png")

        image = mapper.get_next_available_image(1, exclude_used=False)
        assert image == "images/page1_img1.png"

    def test_get_next_image_empty_page(self):
        """Deve retornar None para página sem imagens"""
        mapper = ImageReferenceMapper()
        image = mapper.get_next_available_image(999)
        assert image is None

    def test_get_next_image_all_used(self):
        """Deve retornar None quando todas as imagens estão mapeadas"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/page1_img1.png")
        mapper.map_image_to_reference("figura", 1, "images/page1_img1.png")

        image = mapper.get_next_available_image(1, exclude_used=True)
        assert image is None


class TestInjectImagesToText:
    """Testes para injetar imagens no texto"""

    def test_inject_single_image(self):
        """Deve injetar uma imagem no texto"""
        mapper = ImageReferenceMapper()
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")

        text = "Conforme mostrado na figura 1. Este é o resultado."
        result = mapper.inject_images_into_text(text)

        assert "![Figura 1](images/fig1.png)" in result

    def test_inject_multiple_images(self):
        """Deve injetar múltiplas imagens"""
        mapper = ImageReferenceMapper()
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")
        mapper.map_image_to_reference("figura", 2, "images/fig2.png")

        text = "Figura 1 mostra X. Figura 2 mostra Y."
        result = mapper.inject_images_into_text(text)

        assert "![Figura 1](images/fig1.png)" in result
        assert "![Figura 2](images/fig2.png)" in result

    def test_inject_no_references(self):
        """Deve retornar texto original sem referências"""
        mapper = ImageReferenceMapper()
        text = "Texto sem referências de imagens"
        result = mapper.inject_images_into_text(text)
        assert result == text

    def test_inject_preserves_original(self):
        """Deve preservar texto original ao injetar"""
        mapper = ImageReferenceMapper()
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")

        text = "Conforme mostrado na figura 1. Este é o resultado."
        result = mapper.inject_images_into_text(text)

        # Texto original deve estar presente
        assert "Conforme mostrado na figura 1" in result
        assert "Este é o resultado" in result


class TestAutoAssignImagesToReferences:
    """Testes para atribuição automática de imagens"""

    def test_auto_assign_single(self):
        """Deve atribuir automaticamente uma imagem"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/fig1.png")
        mapper.find_references_in_text("Figura 1 mostra X.", page_num=1)

        result = mapper.auto_assign_images_to_references(1)
        assert ("figura", 1) in result

    def test_auto_assign_multiple(self):
        """Deve atribuir múltiplas imagens automaticamente"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/fig1.png")
        mapper.add_image(1, "images/fig2.png")
        mapper.add_image(1, "images/fig3.png")
        mapper.find_references_in_text("Figura 1. Figura 2. Figura 3.")

        result = mapper.auto_assign_images_to_references(1)
        assert len(result) >= 3

    def test_auto_assign_respects_order(self):
        """Deve respeitar ordem de aparição"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/first.png")
        mapper.add_image(1, "images/second.png")
        mapper.find_references_in_text("Figura 1 e Figura 2")

        result = mapper.auto_assign_images_to_references(1)
        # Primeira referência deve receber primeira imagem
        assert result.get(("figura", 1)) == "images/first.png"

    def test_auto_assign_more_images_than_refs(self):
        """Deve lidar com mais imagens que referências"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/fig1.png")
        mapper.add_image(1, "images/fig2.png")
        mapper.add_image(1, "images/fig3.png")
        mapper.find_references_in_text("Figura 1.")

        result = mapper.auto_assign_images_to_references(1)
        assert len(result) == 1

    def test_auto_assign_more_refs_than_images(self):
        """Deve lidar com mais referências que imagens"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/fig1.png")
        mapper.find_references_in_text("Figura 1. Figura 2. Figura 3.")

        result = mapper.auto_assign_images_to_references(1)
        assert len(result) == 1


class TestGetStatistics:
    """Testes para estatísticas do mapeador"""

    def test_statistics_empty_mapper(self):
        """Deve retornar estatísticas zero para mapeador vazio"""
        mapper = ImageReferenceMapper()
        stats = mapper.get_statistics()

        assert stats["total_references"] == 0
        assert stats["total_images_extracted"] == 0
        assert stats["images_mapped"] == 0
        assert stats["unmapped_references"] == 0

    def test_statistics_with_data(self):
        """Deve retornar estatísticas corretas com dados"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/fig1.png")
        mapper.add_image(1, "images/fig2.png")
        mapper.find_references_in_text("Figura 1. Figura 2. Figura 3.")
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")

        stats = mapper.get_statistics()
        assert stats["total_images_extracted"] == 2
        assert stats["images_mapped"] == 1
        assert stats["unmapped_references"] >= 2

    def test_statistics_structure(self):
        """Deve retornar estrutura correta"""
        mapper = ImageReferenceMapper()
        stats = mapper.get_statistics()

        required_keys = [
            "total_references",
            "total_images_extracted",
            "images_mapped",
            "unmapped_references"
        ]
        for key in required_keys:
            assert key in stats
            assert isinstance(stats[key], int)


class TestReset:
    """Testes para resetar o mapeador"""

    def test_reset_clears_data(self):
        """Deve limpar todos os dados"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/fig1.png")
        mapper.find_references_in_text("Figura 1")
        mapper.map_image_to_reference("figura", 1, "images/fig1.png")

        # Verificar que tem dados
        assert len(mapper.references) > 0
        assert len(mapper.image_map) > 0
        assert len(mapper.page_images) > 0

        # Reset
        mapper.reset()

        # Verificar que foi zerado
        assert len(mapper.references) == 0
        assert len(mapper.image_map) == 0
        assert len(mapper.page_images) == 0

    def test_reset_allows_reuse(self):
        """Deve permitir reutilização após reset"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "images/fig1.png")
        mapper.reset()

        # Deve funcionar normalmente após reset
        mapper.add_image(1, "images/fig2.png")
        assert mapper.page_images[1][0] == "images/fig2.png"


class TestIntegrationScenarios:
    """Testes de integração com cenários complexos"""

    def test_full_workflow(self):
        """Deve funcionar em um fluxo completo"""
        mapper = ImageReferenceMapper()

        # 1. Adicionar imagens extraídas
        mapper.add_image(1, "images/page1_img1.png")
        mapper.add_image(1, "images/page1_img2.png")
        mapper.add_image(2, "images/page2_img1.png")

        # 2. Encontrar referências
        text_page1 = "Figura 1 mostra o resultado principal. Tabela 1 apresenta os dados."
        text_page2 = "Figura 2 é uma comparação."

        mapper.find_references_in_text(text_page1, page_num=1)
        mapper.find_references_in_text(text_page2, page_num=2)

        # 3. Mapear automaticamente
        mapper.auto_assign_images_to_references(1)
        mapper.auto_assign_images_to_references(2)

        # 4. Injetar no texto
        result1 = mapper.inject_images_into_text(text_page1, page_num=1)
        result2 = mapper.inject_images_into_text(text_page2, page_num=2)

        # 5. Verificar estatísticas
        stats = mapper.get_statistics()
        assert stats["total_references"] > 0
        assert stats["total_images_extracted"] > 0

    def test_multiple_page_workflow(self):
        """Deve funcionar com múltiplas páginas"""
        mapper = ImageReferenceMapper()

        # Adicionar imagens de 3 páginas
        for page in range(1, 4):
            mapper.add_image(page, f"images/page{page}_img1.png")
            mapper.add_image(page, f"images/page{page}_img2.png")

        # Encontrar referências em cada página
        for page in range(1, 4):
            text = f"Página {page}: Figura 1 e Figura 2"
            mapper.find_references_in_text(text, page_num=page)

        # Mapear cada página
        for page in range(1, 4):
            mapper.auto_assign_images_to_references(page)

        # Verificar que todas as páginas foram processadas
        stats = mapper.get_statistics()
        assert stats["total_images_extracted"] == 6

    def test_mixed_reference_types(self):
        """Deve lidar com tipos de referência mistos"""
        mapper = ImageReferenceMapper()
        mapper.add_image(1, "img1.png")
        mapper.add_image(1, "img2.png")
        mapper.add_image(1, "img3.png")

        text = "Figura 1, Tabela 1, Gráfico 1"
        refs = mapper.find_references_in_text(text)

        assert any(r.ref_type == "figura" for r in refs)
        assert any(r.ref_type == "tabela" for r in refs)
        assert any(r.ref_type == "gráfico" for r in refs)
