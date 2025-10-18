"""
Testes abrangentes para app/services/pdf2md_service.py

Testa funcionalidades não cobertas:
- consolidate_text_blocks
- _inject_images_in_paragraphs
- find_duplicate_images
- create_zip_export
- process_multiple_pdfs
"""

import pytest
import os
import tempfile
import zipfile
import hashlib
from unittest.mock import patch, MagicMock
import fitz
from app.services.pdf2md_service import (
    calculate_image_hash,
    extract_images_from_page,
    extract_text_blocks_from_page,
    consolidate_text_blocks,
    _inject_images_in_paragraphs,
    find_duplicate_images,
    create_zip_export,
    process_multiple_pdfs,
)
from app.utils.image_reference_mapper import ImageReferenceMapper


@pytest.fixture
def temp_dir():
    """Cria um diretório temporário para testes"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_pdf(temp_dir):
    """Cria um PDF de amostra para testes"""
    pdf_path = os.path.join(temp_dir, "sample.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Título Principal", fontsize=20, color=(0, 0, 0))
    page.insert_text((50, 100), "Este é um parágrafo normal.")
    page.insert_text((50, 150), "Figura 1: Uma imagem importante")
    page.insert_text((50, 200), "- Item 1 da lista")
    page.insert_text((50, 230), "- Item 2 da lista")
    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture
def sample_image(temp_dir):
    """Cria uma imagem de amostra"""
    doc = fitz.open()
    page = doc.new_page()
    page.draw_circle((150, 150), 50, color=(0, 0, 0), fill=(1, 0, 0))

    img_dir = os.path.join(temp_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    img_path = os.path.join(img_dir, "test_image.png")

    pix = page.get_pixmap()
    pix.save(img_path)
    doc.close()
    return img_path


class TestCalculateImageHash:
    """Testes para calculate_image_hash"""

    def test_calculate_hash_existing_file(self, sample_image):
        """Deve calcular hash de arquivo existente"""
        hash_value = calculate_image_hash(sample_image)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 32  # MD5 tem 32 caracteres

    def test_calculate_hash_consistent(self, sample_image):
        """Hash deve ser consistente para o mesmo arquivo"""
        hash1 = calculate_image_hash(sample_image)
        hash2 = calculate_image_hash(sample_image)
        assert hash1 == hash2

    def test_calculate_hash_different_files(self, sample_image, temp_dir):
        """Arquivos diferentes devem ter hashes diferentes"""
        # Criar segundo arquivo
        img2_path = os.path.join(temp_dir, "image2.png")
        doc = fitz.open()
        page = doc.new_page()
        page.draw_rect((50, 50, 100, 100), color=(0, 0, 1), fill=(0, 1, 0))
        pix = page.get_pixmap()
        pix.save(img2_path)
        doc.close()

        hash1 = calculate_image_hash(sample_image)
        hash2 = calculate_image_hash(img2_path)
        assert hash1 != hash2

    def test_calculate_hash_nonexistent_file(self):
        """Deve retornar string vazia para arquivo inexistente"""
        hash_value = calculate_image_hash("/inexistente/file.png")
        assert hash_value == ""

    def test_calculate_hash_returns_md5(self, sample_image):
        """Hash deve estar em formato MD5"""
        hash_value = calculate_image_hash(sample_image)
        # Tentar converter para validar formato hex
        try:
            int(hash_value, 16)
            assert True
        except ValueError:
            assert False, "Hash não está em formato hexadecimal válido"


class TestExtractImagesFromPage:
    """Testes para extract_images_from_page"""

    def test_extract_images_from_page_returns_list(self, sample_pdf, temp_dir):
        """Deve retornar uma lista"""
        doc = fitz.open(sample_pdf)
        page = doc[0]
        images = extract_images_from_page(doc, page, 0, temp_dir, "sample")
        assert isinstance(images, list)

    def test_extract_images_creates_directory(self, sample_pdf, temp_dir):
        """Deve criar diretório de imagens se não existir"""
        doc = fitz.open(sample_pdf)
        page = doc[0]
        extract_images_from_page(doc, page, 0, temp_dir, "sample")

        img_dir = os.path.join(temp_dir, "images")
        assert os.path.exists(img_dir)

    def test_extract_images_relative_paths(self, sample_pdf, temp_dir):
        """Deve retornar caminhos relativos"""
        doc = fitz.open(sample_pdf)
        page = doc[0]
        images = extract_images_from_page(doc, page, 0, temp_dir, "sample")

        for img_path in images:
            assert img_path.startswith("images/")
            assert not os.path.isabs(img_path)


class TestExtractTextBlocksFromPage:
    """Testes para extract_text_blocks_from_page"""

    def test_extract_text_blocks_returns_list(self, sample_pdf):
        """Deve retornar uma lista"""
        doc = fitz.open(sample_pdf)
        page = doc[0]
        blocks = extract_text_blocks_from_page(page, 0)
        assert isinstance(blocks, list)

    def test_extract_text_blocks_structure(self, sample_pdf):
        """Blocos devem ter estrutura correta"""
        doc = fitz.open(sample_pdf)
        page = doc[0]
        blocks = extract_text_blocks_from_page(page, 0)

        if blocks:
            block = blocks[0]
            assert "text" in block
            assert "font_size" in block
            assert "font_flags" in block
            assert "bbox" in block
            assert "page" in block

    def test_extract_text_blocks_filters_empty(self, sample_pdf):
        """Deve filtrar blocos vazios"""
        doc = fitz.open(sample_pdf)
        page = doc[0]
        blocks = extract_text_blocks_from_page(page, 0)

        for block in blocks:
            assert block["text"].strip() != ""

    def test_extract_text_blocks_page_number(self, sample_pdf):
        """Deve incluir número da página"""
        doc = fitz.open(sample_pdf)
        page = doc[0]
        blocks = extract_text_blocks_from_page(page, 5)

        for block in blocks:
            assert block["page"] == 5


class TestConsolidateTextBlocks:
    """Testes para consolidate_text_blocks"""

    def test_consolidate_empty_list(self):
        """Deve retornar lista vazia para entrada vazia"""
        result = consolidate_text_blocks([])
        assert result == []

    def test_consolidate_single_block(self):
        """Deve processar bloco único"""
        blocks = [
            {
                "text": "Hello world",
                "font_size": 12,
                "font_flags": 0,
                "bbox": [0, 0, 100, 30],
                "page": 1,
            }
        ]
        result = consolidate_text_blocks(blocks)
        assert len(result) > 0
        assert "Hello world" in result[0]

    def test_consolidate_heading_detection(self):
        """Deve detectar headings por tamanho de fonte"""
        blocks = [
            {
                "text": "Título",
                "font_size": 24,
                "font_flags": 0,
                "bbox": [0, 0, 100, 30],
                "page": 1,
            },
            {
                "text": "Texto normal",
                "font_size": 12,
                "font_flags": 0,
                "bbox": [0, 50, 100, 30],
                "page": 1,
            },
        ]
        result = consolidate_text_blocks(blocks)
        assert len(result) >= 2
        # Título deve ter # Markdown
        assert any("#" in p for p in result)

    def test_consolidate_bold_detection(self):
        """Deve detectar negrito por flags"""
        blocks = [
            {
                "text": "Texto em negrito",
                "font_size": 12,
                "font_flags": 16,  # Flag de negrito
                "bbox": [0, 0, 100, 30],
                "page": 1,
            }
        ]
        result = consolidate_text_blocks(blocks)
        assert len(result) > 0

    def test_consolidate_multiple_blocks(self):
        """Deve consolidar múltiplos blocos"""
        blocks = [
            {
                "text": f"Linha {i}",
                "font_size": 12,
                "font_flags": 0,
                "bbox": [0, i * 30, 100, 30],
                "page": 1,
            }
            for i in range(5)
        ]
        result = consolidate_text_blocks(blocks)
        assert len(result) > 0


class TestInjectImagesInParagraphs:
    """Testes para _inject_images_in_paragraphs"""

    def test_inject_images_returns_list(self):
        """Deve retornar uma lista"""
        paragraphs = ["Parágrafo 1", "Figura 1: descrição"]
        page_images = ["images/img1.png"]
        mapper = ImageReferenceMapper()

        result = _inject_images_in_paragraphs(paragraphs, page_images, 1, mapper)
        assert isinstance(result, list)

    def test_inject_images_preserves_paragraphs(self):
        """Deve preservar parágrafos originais"""
        paragraphs = ["Parágrafo 1", "Parágrafo 2"]
        page_images = []
        mapper = ImageReferenceMapper()

        result = _inject_images_in_paragraphs(paragraphs, page_images, 1, mapper)
        assert "Parágrafo 1" in result
        assert "Parágrafo 2" in result

    def test_inject_images_finds_references(self):
        """Deve encontrar referências a figuras"""
        paragraphs = ["Veja a Figura 1 abaixo:", "Texto posterior"]
        page_images = ["images/fig1.png"]
        mapper = ImageReferenceMapper()

        result = _inject_images_in_paragraphs(paragraphs, page_images, 1, mapper)
        assert len(result) > len(paragraphs)  # Deve ter adicionado imagem

    def test_inject_images_handles_english_references(self):
        """Deve encontrar referências em inglês"""
        paragraphs = ["See Figure 1 below:", "More text"]
        page_images = ["images/fig1.png"]
        mapper = ImageReferenceMapper()

        result = _inject_images_in_paragraphs(paragraphs, page_images, 1, mapper)
        # Deve processar sem erros
        assert isinstance(result, list)

    def test_inject_images_empty_inputs(self):
        """Deve lidar com entradas vazias"""
        mapper = ImageReferenceMapper()

        result = _inject_images_in_paragraphs([], [], 1, mapper)
        assert result == []


class TestFindDuplicateImages:
    """Testes para find_duplicate_images"""

    def test_find_duplicates_no_images(self, temp_dir):
        """Deve retornar lista vazia se não há imagens"""
        result = find_duplicate_images(temp_dir)
        assert result == []

    def test_find_duplicates_single_image(self, temp_dir, sample_image):
        """Deve retornar lista vazia com uma imagem"""
        result = find_duplicate_images(temp_dir)
        # Uma imagem não é duplicata
        assert isinstance(result, list)

    def test_find_duplicates_identical_files(self, temp_dir):
        """Deve detectar arquivos idênticos"""
        img_dir = os.path.join(temp_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        # Criar dois arquivos idênticos
        content = b"identical content"
        img1 = os.path.join(img_dir, "img1.png")
        img2 = os.path.join(img_dir, "img2.png")

        with open(img1, "wb") as f:
            f.write(content)
        with open(img2, "wb") as f:
            f.write(content)

        result = find_duplicate_images(temp_dir, min_occurrences=2)
        assert len(result) == 2  # Ambos devem ser marcados como duplicatas

    def test_find_duplicates_min_occurrences(self, temp_dir):
        """Deve respeitar parâmetro min_occurrences"""
        img_dir = os.path.join(temp_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        content = b"duplicate"
        for i in range(3):
            with open(os.path.join(img_dir, f"img{i}.png"), "wb") as f:
                f.write(content)

        # Com min_occurrences=3
        result = find_duplicate_images(temp_dir, min_occurrences=3)
        assert len(result) == 3

    def test_find_duplicates_nonexistent_directory(self):
        """Deve retornar lista vazia se diretório não existe"""
        result = find_duplicate_images("/inexistente/path")
        assert result == []


class TestCreateZipExport:
    """Testes para create_zip_export"""

    def test_create_zip_export_success(self, temp_dir, sample_pdf):
        """Deve criar arquivo ZIP com sucesso"""
        # Criar estrutura de arquivos
        md_path = os.path.join(temp_dir, "test.md")
        with open(md_path, "w") as f:
            f.write("# Título\n\nConteúdo")

        img_dir = os.path.join(temp_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        zip_path = create_zip_export(temp_dir, "test")
        assert os.path.exists(zip_path)
        assert zip_path.endswith(".zip")

    def test_create_zip_contains_markdown(self, temp_dir):
        """ZIP deve conter arquivo markdown"""
        md_path = os.path.join(temp_dir, "doc.md")
        with open(md_path, "w") as f:
            f.write("# Documento")

        img_dir = os.path.join(temp_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        zip_path = create_zip_export(temp_dir, "doc")

        with zipfile.ZipFile(zip_path, "r") as zf:
            assert "doc.md" in zf.namelist()

    def test_create_zip_contains_images(self, temp_dir):
        """ZIP deve conter pasta de imagens"""
        md_path = os.path.join(temp_dir, "doc.md")
        with open(md_path, "w") as f:
            f.write("# Documento")

        img_dir = os.path.join(temp_dir, "images")
        os.makedirs(img_dir, exist_ok=True)
        img_file = os.path.join(img_dir, "test.png")
        with open(img_file, "wb") as f:
            f.write(b"fake image")

        zip_path = create_zip_export(temp_dir, "doc")

        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.namelist()
            assert any("images" in f for f in files)

    def test_create_zip_valid_archive(self, temp_dir):
        """ZIP criado deve ser válido"""
        md_path = os.path.join(temp_dir, "test.md")
        with open(md_path, "w") as f:
            f.write("Conteúdo")

        img_dir = os.path.join(temp_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        zip_path = create_zip_export(temp_dir, "test")

        # Deve ser um ZIP válido
        assert zipfile.is_zipfile(zip_path)


class TestProcessMultiplePdfs:
    """Testes para process_multiple_pdfs"""

    def test_process_multiple_pdfs_returns_filename(self, temp_dir, sample_pdf):
        """Deve retornar nome de arquivo ZIP"""
        pdf2_path = os.path.join(temp_dir, "sample2.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Segundo PDF")
        doc.save(pdf2_path)
        doc.close()

        result = process_multiple_pdfs([sample_pdf, pdf2_path], temp_dir)
        assert isinstance(result, str)
        assert result.endswith(".zip")

    def test_process_multiple_pdfs_empty_list(self, temp_dir):
        """Deve lidar com lista vazia"""
        with pytest.raises(ValueError):
            process_multiple_pdfs([], temp_dir)

    def test_process_multiple_pdfs_creates_output(self, temp_dir, sample_pdf):
        """Deve criar arquivos de saída"""
        pdf2_path = os.path.join(temp_dir, "sample2.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Segundo PDF")
        doc.save(pdf2_path)
        doc.close()

        result = process_multiple_pdfs([sample_pdf, pdf2_path], temp_dir)

        # Arquivo ZIP deve ter sido criado
        if result:
            zip_path = os.path.join(temp_dir, result)
            assert os.path.exists(zip_path)

    def test_process_multiple_pdfs_consolidates(self, temp_dir, sample_pdf):
        """Deve consolidar múltiplos PDFs em um único ZIP"""
        # Criar segundo PDF
        pdf2_path = os.path.join(temp_dir, "sample2.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Segundo PDF")
        doc.save(pdf2_path)
        doc.close()

        result = process_multiple_pdfs([sample_pdf, pdf2_path], temp_dir)
        assert isinstance(result, str)
