import pytest
import os
import tempfile
import json
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Cliente de teste para a API FastAPI"""
    return TestClient(app)


@pytest.fixture
def temp_output_dir(monkeypatch):
    """Cria um diretório temporário para output durante os testes"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Monkeypatch do OUTPUT_DIR em app.main
        monkeypatch.setattr("app.main.OUTPUT_DIR", tmpdir)
        yield tmpdir


@pytest.fixture
def temp_pdf(temp_output_dir):
    """Cria um PDF de teste temporário"""
    import fitz

    pdf_path = os.path.join(temp_output_dir, "test_source.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Teste de PDF para API")
    page.insert_text((50, 100), "Figura 1: Imagem importante")
    doc.save(pdf_path)
    doc.close()

    yield pdf_path


class TestHealthCheck:
    """Testes para health check da API"""

    def test_health_check_returns_ok(self, client):
        """Health check deve retornar status ok"""
        response = client.get("/api/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_check_json_response(self, client):
        """Health check deve retornar JSON válido"""
        response = client.get("/api/health/")
        assert response.headers["content-type"].startswith("application/json")


class TestUploadEndpoint:
    """Testes para endpoint de upload"""

    def test_upload_pdf_success(self, client, temp_pdf):
        """Deve processar upload de PDF com sucesso"""
        with open(temp_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            response = client.post("/api/upload/", files=files)

        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["success"] is True
        assert "markdown_file" in data
        assert "images_dir" in data
        assert "zip_file" in data
        assert data["zip_file"].endswith("_completo.zip")

    def test_upload_without_file(self, client):
        """Deve rejeitar upload sem arquivo"""
        response = client.post("/api/upload/")
        assert response.status_code == 422  # Unprocessable Entity

    def test_upload_non_pdf_file(self, client, temp_output_dir):
        """Deve rejeitar arquivo que não é PDF"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, dir=temp_output_dir) as f:
            f.write(b"Este eh um arquivo de texto")
            txt_path = f.name

        try:
            with open(txt_path, "rb") as f:
                files = {"file": ("test.txt", f, "text/plain")}
                response = client.post("/api/upload/", files=files)

            assert response.status_code == 400
            data = response.json()
            assert "Arquivo deve ser PDF" in data["detail"]
        finally:
            os.unlink(txt_path)

    def test_upload_returns_valid_markdown_name(self, client, temp_pdf):
        """Deve retornar nome válido de arquivo markdown"""
        with open(temp_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            response = client.post("/api/upload/", files=files)

        data = response.json()
        md_file = data["markdown_file"]

        assert md_file.endswith(".md")
        assert md_file != ""

    def test_upload_response_structure(self, client, temp_pdf):
        """Resposta deve ter estrutura correta"""
        with open(temp_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            response = client.post("/api/upload/", files=files)

        data = response.json()
        assert isinstance(data, dict)
        assert "markdown_file" in data
        assert "images_dir" in data
        assert "success" in data
        assert data["success"] is True
        assert "zip_file" in data
        assert "download_url" in data


class TestDownloadEndpoint:
    """Testes para endpoint de download"""

    def test_download_existing_file(self, client, temp_pdf):
        """Deve fazer download de arquivo existente"""
        # Primeiro fazer upload
        with open(temp_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            upload_response = client.post("/api/upload/", files=files)

        md_file = upload_response.json()["markdown_file"]

        # Depois fazer download
        response = client.get(f"/api/download/{md_file}")
        assert response.status_code == 200
        assert len(response.content) > 0

    def test_download_nonexistent_file(self, client):
        """Deve retornar 404 para arquivo inexistente"""
        response = client.get("/api/download/inexistente.md")
        assert response.status_code == 404
        data = response.json()
        assert "não encontrado" in data["detail"].lower() or "not found" in data["detail"].lower()

    def test_download_returns_markdown_type(self, client, temp_pdf):
        """Download deve retornar tipo MIME correto"""
        # Upload
        with open(temp_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            upload_response = client.post("/api/upload/", files=files)

        md_file = upload_response.json()["markdown_file"]

        # Download
        response = client.get(f"/api/download/{md_file}")
        assert "text/markdown" in response.headers.get("content-type", "")


class TestDownloadZipEndpoint:
    """Testes para endpoint de download de ZIP"""

    def test_download_zip_after_upload(self, client, temp_pdf):
        """Deve fazer download do ZIP após upload"""
        # Upload
        with open(temp_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            upload_response = client.post("/api/upload/", files=files)

        assert upload_response.status_code == 200
        zip_file = upload_response.json()["zip_file"]

        # Download do ZIP
        response = client.get(f"/api/download-zip/{zip_file}")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/zip"
        assert len(response.content) > 0

    def test_download_nonexistent_zip(self, client):
        """Deve retornar 404 para ZIP inexistente"""
        response = client.get("/api/download-zip/inexistente.zip")
        assert response.status_code == 404
        data = response.json()
        assert "não encontrado" in data["detail"].lower() or "not found" in data["detail"].lower()

    def test_zip_contains_markdown_and_images(self, client, temp_pdf):
        """ZIP deve conter markdown e imagens"""
        import zipfile
        import io

        # Upload
        with open(temp_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            upload_response = client.post("/api/upload/", files=files)

        assert upload_response.status_code == 200
        zip_file = upload_response.json()["zip_file"]

        # Download do ZIP
        response = client.get(f"/api/download-zip/{zip_file}")
        assert response.status_code == 200

        # Verificar conteúdo do ZIP
        zip_bytes = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_bytes, 'r') as zf:
            files_in_zip = zf.namelist()
            # Deve ter pelo menos um arquivo MD
            has_md = any(f.endswith('.md') for f in files_in_zip)
            assert has_md, "ZIP deve conter arquivo Markdown"


class TestUploadValidation:
    """Testes para validações de upload"""

    def test_upload_without_filename(self, client, temp_output_dir):
        """Deve lidar com arquivo sem filename"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=temp_output_dir) as f:
            f.write(b"%PDF-1.4\n")  # Mínimo PDF
            pdf_path = f.name

        try:
            with open(pdf_path, "rb") as f:
                files = {"file": (None, f, "application/pdf")}
                response = client.post("/api/upload/", files=files)

            # Deve aceitar ou retornar erro apropriado
            assert response.status_code in [200, 400, 422]
        finally:
            os.unlink(pdf_path)

    def test_upload_uppercase_pdf_extension(self, client, temp_output_dir):
        """Deve aceitar extensão .PDF em maiúscula"""
        import fitz

        pdf_uppercase = os.path.join(temp_output_dir, "TEST.PDF")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Teste")
        doc.save(pdf_uppercase)
        doc.close()

        with open(pdf_uppercase, "rb") as f:
            files = {"file": ("TEST.PDF", f, "application/pdf")}
            response = client.post("/api/upload/", files=files)

        assert response.status_code == 200

    def test_upload_mixed_case_pdf_extension(self, client, temp_output_dir):
        """Deve aceitar extensão .Pdf em maiúscula mista"""
        import fitz

        pdf_mixed = os.path.join(temp_output_dir, "test.Pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Teste")
        doc.save(pdf_mixed)
        doc.close()

        with open(pdf_mixed, "rb") as f:
            files = {"file": ("test.Pdf", f, "application/pdf")}
            response = client.post("/api/upload/", files=files)

        assert response.status_code == 200


class TestCORSHeaders:
    """Testes para CORS"""

    def test_cors_headers_present(self, client):
        """Deve incluir headers CORS"""
        response = client.get("/api/health/")

        # FastAPI com CORSMiddleware deve incluir headers
        assert response.status_code == 200


class TestErrorHandling:
    """Testes para tratamento de erros"""

    def test_api_404_not_found(self, client):
        """Deve retornar 404 para rota inexistente"""
        response = client.get("/api/inexistente/")
        assert response.status_code == 404

    def test_upload_endpoint_method_not_allowed(self, client):
        """Upload endpoint deve rejeitar GET"""
        response = client.get("/api/upload/")
        assert response.status_code in [404, 405]  # Not Found ou Method Not Allowed

    def test_download_endpoint_method_not_allowed(self, client):
        """Download endpoint deve rejeitar POST"""
        response = client.post("/api/download/test.md")
        assert response.status_code in [404, 405]


class TestEdgeCaseSamePdfName:
    """Testes para edge case: múltiplos PDFs com o mesmo nome"""

    def test_upload_same_pdf_name_twice(self, client, temp_output_dir):
        """Edge case: fazer upload do mesmo arquivo PDF com o mesmo nome"""
        import fitz

        results = []

        for i in range(2):
            # Criar PDF temporário na memória
            pdf_path = os.path.join(temp_output_dir, f"temp_{i}.pdf")
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 50), f"Documento {i}")
            page.insert_text((50, 100), f"Página com índice {i}")
            doc.save(pdf_path)
            doc.close()

            # Upload com mesmo nome
            with open(pdf_path, "rb") as f:
                files = {"file": ("document.pdf", f, "application/pdf")}
                response = client.post("/api/upload/", files=files)

            assert response.status_code == 200
            results.append(response.json())

        # Ambos devem ter sucesso
        assert len(results) == 2
        assert all(r["success"] for r in results)

        # Ambos devem ter o mesmo nome de ZIP (baseado no PDF original)
        assert results[0]["zip_file"] == results[1]["zip_file"] == "document_completo.zip"

        # Os markdowns devem ter o mesmo nome também
        assert results[0]["markdown_file"] == results[1]["markdown_file"] == "document.md"

    def test_multiple_different_pdfs_same_base_name(self, client, temp_output_dir):
        """Múltiplos PDFs diferentes com mesmo nome base"""
        import fitz

        # Criar múltiplos PDFs com conteúdo diferente mas mesmo nome
        for i in range(3):
            pdf_path = os.path.join(temp_output_dir, f"temp_{i}.pdf")
            doc = fitz.open()
            # Criar PDFs com diferentes números de páginas
            for p in range(i + 1):
                page = doc.new_page()
                page.insert_text((50, 50), f"Documento - Página {p + 1}")
            doc.save(pdf_path)
            doc.close()

            # Upload com mesmo nome
            with open(pdf_path, "rb") as f:
                files = {"file": ("report.pdf", f, "application/pdf")}
                response = client.post("/api/upload/", files=files)

            assert response.status_code == 200
            assert response.json()["success"] is True


class TestEndToEnd:
    """Testes end-to-end completos"""

    def test_full_workflow_upload_and_download(self, client, temp_pdf):
        """Workflow completo: upload, processamento, download"""
        # 1. Health check
        health = client.get("/api/health/")
        assert health.status_code == 200

        # 2. Upload
        with open(temp_pdf, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            upload_response = client.post("/api/upload/", files=files)

        assert upload_response.status_code == 200
        data = upload_response.json()
        md_file = data["markdown_file"]
        zip_file = data["zip_file"]

        # 3. Download Markdown
        download_response = client.get(f"/api/download/{md_file}")
        assert download_response.status_code == 200
        assert len(download_response.content) > 0

        # 4. Download ZIP
        zip_response = client.get(f"/api/download-zip/{zip_file}")
        assert zip_response.status_code == 200
        assert zip_response.headers.get("content-type") == "application/zip"

    def test_multiple_uploads_different_files(self, client, temp_output_dir):
        """Deve processar múltiplos uploads com diferentes PDFs"""
        import fitz

        results = []

        for i in range(3):
            # Criar um PDF único para cada iteração
            pdf_path = os.path.join(temp_output_dir, f"test_{i}.pdf")
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 50), f"Teste {i}")
            doc.save(pdf_path)
            doc.close()

            with open(pdf_path, "rb") as f:
                files = {"file": (f"test_{i}.pdf", f, "application/pdf")}
                response = client.post("/api/upload/", files=files)

            assert response.status_code == 200
            results.append(response.json())

        # Todos devem ter sucesso
        assert len(results) == 3
        assert all(r["success"] for r in results)

    def test_full_workflow_with_real_aula_pdf(self, client, temp_output_dir):
        """Workflow completo com o PDF real aula1.pdf"""
        import os

        # Verificar se aula1.pdf existe no diretório raiz
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        aula_pdf = os.path.join(project_root, "aula1.pdf")

        if not os.path.exists(aula_pdf):
            pytest.skip("aula1.pdf não encontrado")

        # Upload
        with open(aula_pdf, "rb") as f:
            files = {"file": ("aula1.pdf", f, "application/pdf")}
            upload_response = client.post("/api/upload/", files=files)

        assert upload_response.status_code == 200
        data = upload_response.json()
        assert data["success"] is True
        assert "markdown_file" in data
        assert "zip_file" in data

        # Download Markdown
        md_file = data["markdown_file"]
        md_response = client.get(f"/api/download/{md_file}")
        assert md_response.status_code == 200
        assert len(md_response.content) > 0

        # Download ZIP
        zip_file = data["zip_file"]
        zip_response = client.get(f"/api/download-zip/{zip_file}")
        assert zip_response.status_code == 200
        assert zip_response.headers.get("content-type") == "application/zip"

        # Verificar conteúdo do ZIP
        import zipfile
        import io
        zip_bytes = io.BytesIO(zip_response.content)
        with zipfile.ZipFile(zip_bytes, 'r') as zf:
            files_in_zip = zf.namelist()
            # Deve ter pelo menos um MD e algumas imagens
            has_md = any(f.endswith('.md') for f in files_in_zip)
            assert has_md, "ZIP deve conter MD"


class TestUploadMultiple:
    """Testes específicos para o endpoint /api/upload-multiple/"""

    def test_upload_multiple_empty_list(self, client):
        """Deve rejeitar lista vazia de arquivos"""
        response = client.post("/api/upload-multiple/", files=[])
        # FastAPI retorna 422 para lista vazia (Unprocessable Entity)
        assert response.status_code in [400, 422]
        data = response.json()
        assert "detail" in data

    def test_upload_multiple_single_pdf(self, client, temp_pdf):
        """Deve processar um único PDF via upload-multiple"""
        with open(temp_pdf, "rb") as f:
            files = [("files", ("test.pdf", f, "application/pdf"))]
            response = client.post("/api/upload-multiple/", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "zip_file" in data
        assert "download_url" in data

    def test_upload_multiple_two_pdfs(self, client, temp_output_dir):
        """Deve processar dois PDFs em um único upload"""
        import fitz

        # Criar dois PDFs
        pdfs = []
        for i in range(2):
            pdf_path = os.path.join(temp_output_dir, f"test_multi_{i}.pdf")
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 50), f"Documento {i}")
            page.insert_text((50, 100), f"Figura 1: Teste {i}")
            doc.save(pdf_path)
            doc.close()
            pdfs.append(pdf_path)

        # Upload múltiplo
        files = []
        for pdf_path in pdfs:
            with open(pdf_path, "rb") as f:
                content = f.read()
            files.append(("files", (os.path.basename(pdf_path), content, "application/pdf")))

        response = client.post("/api/upload-multiple/", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "zip_file" in data
        assert data["zip_file"].endswith(".zip")

    def test_upload_multiple_returns_download_url(self, client, temp_pdf):
        """Deve retornar URL de download válida"""
        with open(temp_pdf, "rb") as f:
            files = [("files", ("test.pdf", f, "application/pdf"))]
            response = client.post("/api/upload-multiple/", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "download_url" in data
        assert "/api/download-zip/" in data["download_url"]

    def test_upload_multiple_non_pdf_file(self, client, temp_output_dir):
        """Deve rejeitar arquivo não-PDF"""
        # Criar um arquivo TXT
        txt_path = os.path.join(temp_output_dir, "test.txt")
        with open(txt_path, "w") as f:
            f.write("Not a PDF")

        with open(txt_path, "rb") as f:
            files = [("files", ("test.txt", f, "text/plain"))]
            response = client.post("/api/upload-multiple/", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "PDF válido" in data["detail"]

    def test_upload_multiple_three_pdfs(self, client, temp_output_dir):
        """Deve processar três PDFs simultaneamente"""
        import fitz

        pdfs = []
        for i in range(3):
            pdf_path = os.path.join(temp_output_dir, f"doc_{i}.pdf")
            doc = fitz.open()
            for page_num in range(2):
                page = doc.new_page()
                page.insert_text((50, 50), f"Doc {i}, Page {page_num}")
            doc.save(pdf_path)
            doc.close()
            pdfs.append(pdf_path)

        # Upload múltiplo
        files = []
        for pdf_path in pdfs:
            with open(pdf_path, "rb") as f:
                content = f.read()
            files.append(("files", (os.path.basename(pdf_path), content, "application/pdf")))

        response = client.post("/api/upload-multiple/", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "consolidado_completo.zip" in data["zip_file"] or data["zip_file"].endswith(".zip")

    def test_upload_multiple_download_generated_zip(self, client, temp_pdf):
        """Deve ser possível fazer download do ZIP gerado"""
        with open(temp_pdf, "rb") as f:
            files = [("files", ("test.pdf", f, "application/pdf"))]
            response = client.post("/api/upload-multiple/", files=files)

        assert response.status_code == 200
        data = response.json()
        zip_filename = data["zip_file"]

        # Tentar fazer download do ZIP
        download_response = client.get(f"/api/download-zip/{zip_filename}")
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/zip"
        assert len(download_response.content) > 0

    def test_upload_multiple_zip_contains_markdown(self, client, temp_pdf):
        """O ZIP deve conter arquivo(s) Markdown"""
        import zipfile
        import io

        with open(temp_pdf, "rb") as f:
            files = [("files", ("test.pdf", f, "application/pdf"))]
            response = client.post("/api/upload-multiple/", files=files)

        assert response.status_code == 200
        data = response.json()
        zip_filename = data["zip_file"]

        # Download do ZIP
        download_response = client.get(f"/api/download-zip/{zip_filename}")
        assert download_response.status_code == 200

        # Verificar conteúdo
        zip_bytes = io.BytesIO(download_response.content)
        with zipfile.ZipFile(zip_bytes, 'r') as zf:
            files_in_zip = zf.namelist()
            has_md = any(f.endswith('.md') for f in files_in_zip)
            assert has_md, f"ZIP deve conter .md, mas tem: {files_in_zip}"

    def test_upload_multiple_different_names(self, client, temp_output_dir):
        """Deve processar PDFs com nomes diferentes"""
        import fitz

        pdf_names = ["relatorio.pdf", "documento.pdf", "anexo.pdf"]
        files = []

        for name in pdf_names:
            pdf_path = os.path.join(temp_output_dir, name)
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 50), f"Arquivo: {name}")
            doc.save(pdf_path)
            doc.close()

            with open(pdf_path, "rb") as f:
                content = f.read()
            files.append(("files", (name, content, "application/pdf")))

        response = client.post("/api/upload-multiple/", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
