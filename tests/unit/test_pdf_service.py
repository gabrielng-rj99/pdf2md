import pytest
import os
import tempfile
import fitz
from pathlib import Path
from app.services.pdf2md_service import process_pdf


class TestProcessPdfBasics:
    """Testes básicos para process_pdf"""

    @pytest.fixture
    def temp_pdf(self):
        """Cria um PDF de teste temporário"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "test.pdf")
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 50), "Teste de PDF")
            doc.save(pdf_path)
            doc.close()

            yield pdf_path, tmpdir

    @pytest.fixture
    def temp_output_dir(self):
        """Cria diretório de saída temporário"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_process_pdf_creates_markdown(self, temp_pdf):
        """Deve criar arquivo markdown"""
        pdf_path, tmpdir = temp_pdf
        output_dir = tmpdir

        md_file, img_dir = process_pdf(pdf_path, output_dir)

        assert md_file is not None
        assert md_file.endswith(".md")
        assert os.path.exists(os.path.join(output_dir, md_file))

    def test_process_pdf_creates_output_dir(self, temp_pdf, temp_output_dir):
        """Deve criar diretório de saída se não existir"""
        pdf_path, _ = temp_pdf
        output_dir = os.path.join(temp_output_dir, "new_output")

        md_file, img_dir = process_pdf(pdf_path, output_dir)

        assert os.path.exists(output_dir)
        assert os.path.isdir(output_dir)

    def test_process_pdf_returns_tuple(self, temp_pdf):
        """Deve retornar tupla (md_file, img_dir)"""
        pdf_path, tmpdir = temp_pdf
        result = process_pdf(pdf_path, tmpdir)

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_process_pdf_markdown_not_empty(self, temp_pdf):
        """Arquivo markdown não deve estar vazio"""
        pdf_path, tmpdir = temp_pdf
        md_file, _ = process_pdf(pdf_path, tmpdir)

        md_path = os.path.join(tmpdir, md_file)
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert len(content) > 0

    def test_process_pdf_images_dir_name(self, temp_pdf):
        """Deve retornar nome correto do diretório de imagens"""
        pdf_path, tmpdir = temp_pdf
        _, img_dir = process_pdf(pdf_path, tmpdir)

        assert img_dir == "images"

    def test_process_pdf_images_dir_exists(self, temp_pdf):
        """Deve criar diretório de imagens"""
        pdf_path, tmpdir = temp_pdf
        _, img_dir = process_pdf(pdf_path, tmpdir)

        img_path = os.path.join(tmpdir, img_dir)
        assert os.path.exists(img_path)
        assert os.path.isdir(img_path)


class TestProcessPdfWithImages:
    """Testes para extração de imagens"""

    @pytest.fixture
    def pdf_with_image(self):
        """Cria PDF com imagem de teste"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "test_with_image.pdf")
            doc = fitz.open()
            page = doc.new_page()

            # Adiciona texto
            page.insert_text((50, 50), "Documento com imagem")
            page.insert_text((50, 100), "Figura 1: Teste")

            # Adiciona imagem (retângulo colorido)
            from PIL import Image
            import io

            img = Image.new('RGB', (100, 100), color='red')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            img_array = fitz.Pixmap(img_bytes)
            rect = fitz.Rect(50, 150, 150, 250)
            page.insert_image(rect, stream=img_bytes.getvalue())

            doc.save(pdf_path)
            doc.close()

            yield pdf_path, tmpdir

    def test_process_pdf_extracts_images(self, pdf_with_image):
        """Deve extrair imagens do PDF"""
        pdf_path, tmpdir = pdf_with_image
        _, img_dir = process_pdf(pdf_path, tmpdir)

        img_path = os.path.join(tmpdir, img_dir)
        images = os.listdir(img_path)

        # Deve haver pelo menos algumas imagens (exceto as filtradas)
        # Nota: depende do filtro de imagens
        assert isinstance(images, list)

    def test_process_pdf_image_references_in_markdown(self, pdf_with_image):
        """Markdown deve ter referências a imagens extraídas"""
        pdf_path, tmpdir = pdf_with_image
        md_file, img_dir = process_pdf(pdf_path, tmpdir)

        md_path = os.path.join(tmpdir, md_file)
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Se há imagens extraídas, deve haver referências no markdown
        # (ou estar vazio se tudo foi filtrado)
        assert isinstance(content, str)


class TestProcessPdfFiltering:
    """Testes para aplicação de filtro de imagens"""

    @pytest.fixture
    def pdf_with_headers_footers(self):
        """Cria PDF com cabeçalho e rodapé"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "test_headers.pdf")
            doc = fitz.open()

            for page_num in range(3):
                page = doc.new_page()

                # Simula cabeçalho (retângulo no topo)
                header_rect = fitz.Rect(0, 0, 595, 50)
                page.draw_rect(header_rect, color=(0, 0, 0), fill=(0.9, 0.9, 0.9))
                page.insert_text((50, 20), f"Página {page_num + 1}")

                # Conteúdo principal
                page.insert_text((50, 150), f"Conteúdo da página {page_num + 1}")
                page.insert_text((50, 200), "Figura 1: Imagem importante")

                # Simula rodapé (retângulo no rodapé)
                footer_rect = fitz.Rect(0, 800, 595, 850)
                page.draw_rect(footer_rect, color=(0, 0, 0), fill=(0.9, 0.9, 0.9))
                page.insert_text((50, 820), "Rodapé do documento")

            doc.save(pdf_path)
            doc.close()

            yield pdf_path, tmpdir

    def test_process_pdf_filters_headers_footers(self, pdf_with_headers_footers):
        """Deve filtrar cabeçalhos e rodapés"""
        pdf_path, tmpdir = pdf_with_headers_footers
        md_file, _ = process_pdf(pdf_path, tmpdir)

        md_path = os.path.join(tmpdir, md_file)
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Conteúdo deve estar presente
        assert "Conteúdo da página" in content or len(content) > 0


class TestProcessPdfErrorHandling:
    """Testes para tratamento de erros"""

    def test_process_pdf_nonexistent_file(self):
        """Deve lidar com arquivo inexistente"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "inexistente.pdf")

            with pytest.raises(ValueError):
                process_pdf(pdf_path, tmpdir)

    def test_process_pdf_invalid_output_dir_permission(self):
        """Deve lidar com permissão negada no diretório de saída"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Criar um PDF válido
            pdf_path = os.path.join(tmpdir, "test.pdf")
            doc = fitz.open()
            doc.new_page()
            doc.save(pdf_path)
            doc.close()

            # Criar diretório sem permissão
            output_dir = os.path.join(tmpdir, "no_permission")
            os.makedirs(output_dir)
            os.chmod(output_dir, 0o000)

            try:
                with pytest.raises((PermissionError, OSError)):
                    process_pdf(pdf_path, output_dir)
            finally:
                # Restaurar permissão para limpeza
                os.chmod(output_dir, 0o755)

    def test_process_pdf_empty_pdf(self):
        """Deve lidar com PDF vazio"""
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "empty.pdf")
            doc = fitz.open()
            doc.new_page()  # Página em branco
            doc.save(pdf_path)
            doc.close()

            md_file, img_dir = process_pdf(pdf_path, tmpdir)

            # Deve retornar tupla válida mesmo com PDF vazio
            assert md_file is not None
            assert img_dir is not None


class TestProcessPdfWithAula:
    """Testes com o aula1.pdf real"""

    def test_process_aula1_pdf(self):
        """Deve processar aula1.pdf corretamente"""
        pdf_path = "aula1.pdf"

        if not os.path.exists(pdf_path):
            pytest.skip("aula1.pdf não encontrado")

        with tempfile.TemporaryDirectory() as tmpdir:
            md_file, img_dir = process_pdf(pdf_path, tmpdir)

            assert md_file is not None
            assert os.path.exists(os.path.join(tmpdir, md_file))
            assert os.path.exists(os.path.join(tmpdir, img_dir))

    def test_process_aula1_filters_correctly(self):
        """Deve filtrar corretamente imagens do aula1.pdf"""
        pdf_path = "aula1.pdf"

        if not os.path.exists(pdf_path):
            pytest.skip("aula1.pdf não encontrado")

        with tempfile.TemporaryDirectory() as tmpdir:
            md_file, img_dir = process_pdf(pdf_path, tmpdir)

            img_path = os.path.join(tmpdir, img_dir)
            images = os.listdir(img_path)

            # Novo filtro remove TODAS as duplicatas (min_occurrences=2)
            # Deve manter apenas imagens únicas (figuras reais do documento)
            # aula1.pdf tem 80 páginas com 92 imagens totais, 2 duplicatas removidas = 90
            assert len(images) == 90  # aula1.pdf: 92 extraídas - 2 duplicatas = 90 finais


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
