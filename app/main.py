from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
import configparser
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.services.pdf2md_service import process_pdf, process_multiple_pdfs

app = FastAPI(
    title="PDF2MD API",
    description="API para converter PDF em Markdown com extração de imagens.",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")

# Load configuration
config = configparser.ConfigParser()
if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE)
else:
    # Default configuration
    config['UPLOAD'] = {'max_file_size_mb': '500'}

MAX_FILE_SIZE_MB = int(config.get('UPLOAD', 'max_file_size_mb', fallback=500))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# IMPORTANTE: Definir rotas de API ANTES de montar o frontend
# Caso contrário, "/" captura tudo

@app.post("/api/upload/", summary="Envie um PDF e receba o Markdown + Imagens em ZIP")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Endpoint para fazer upload de um PDF.
    Retorna informações do arquivo Markdown, imagens e ZIP gerado.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser PDF.")

    # Validar tamanho do arquivo
    if file.size and file.size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo excede o tamanho máximo de {MAX_FILE_SIZE_MB}MB"
        )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_path = os.path.join(OUTPUT_DIR, file.filename)

    try:
        # Salvar PDF temporário
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Arquivo está vazio ou corrompido.")

        try:
            with open(pdf_path, "wb") as f:
                f.write(content)
        except PermissionError:
            raise HTTPException(
                status_code=500,
                detail=f"Erro: Permissão negada ao escrever arquivo. Verifique permissões do diretório de saída ({OUTPUT_DIR})."
            )
        except IOError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Erro de I/O ao salvar arquivo: {str(e)}"
            )

        # Processar PDF
        md_filename, img_dir = process_pdf(pdf_path, OUTPUT_DIR)

        # Obter nome base do PDF para construir nome do ZIP
        pdf_basename = os.path.splitext(file.filename)[0]
        zip_filename = f"{pdf_basename}_completo.zip"

        return JSONResponse({
            "success": True,
            "markdown_file": md_filename,
            "images_dir": img_dir,
            "zip_file": zip_filename,
            "download_url": f"/api/download-zip/{zip_filename}"
        })
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"❌ Erro ao processar PDF: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar PDF: {str(e)}")

@app.post("/api/upload-multiple/", summary="Envie múltiplos PDFs e receba um ZIP consolidado")
async def upload_multiple_pdfs(files: list[UploadFile] = File(...)):
    """
    Endpoint para fazer upload de múltiplos PDFs.
    Processa todos os PDFs com imagens consolidadas em uma única pasta.
    Retorna um ZIP único com todos os Markdowns e imagens.
    """
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="Nenhum arquivo foi enviado.")

    # Validar e salvar arquivos em uma única passagem
    pdf_paths = []
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        for file in files:
            # Validar extensão
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail=f"Arquivo '{file.filename}' não é um PDF válido.")

            # Validar tamanho do arquivo
            if file.size and file.size > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Arquivo '{file.filename}' excede o tamanho máximo de {MAX_FILE_SIZE_MB}MB"
                )

            # Salvar PDF temporário
            pdf_path = os.path.join(OUTPUT_DIR, file.filename)
            try:
                with open(pdf_path, "wb") as f:
                    content = await file.read()
                    if not content:
                        raise HTTPException(status_code=400, detail=f"Arquivo '{file.filename}' está vazio.")
                    f.write(content)
            except PermissionError as pe:
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro: Permissão negada ao escrever arquivo '{file.filename}'. Verifique permissões do diretório de saída ({OUTPUT_DIR})."
                )
            except IOError as ie:
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro ao salvar arquivo '{file.filename}': {str(ie)}"
                )
            pdf_paths.append(pdf_path)

        # Processar múltiplos PDFs
        zip_filename = process_multiple_pdfs(pdf_paths, OUTPUT_DIR)

        return JSONResponse({
            "success": True,
            "zip_file": zip_filename,
            "download_url": f"/api/download-zip/{zip_filename}"
        })
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"❌ Erro ao processar múltiplos PDFs: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar PDFs: {str(e)}")

@app.get("/api/download/{filename}", summary="Baixe o Markdown gerado")
def download_markdown(filename: str):
    """
    Endpoint para baixar o arquivo Markdown gerado.
    """
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    return FileResponse(
        file_path,
        media_type="text/markdown",
        filename=filename
    )

@app.get("/api/download-zip/{filename}", summary="Baixe o arquivo comprimido (Markdown + Imagens)")
def download_zip(filename: str):
    """
    Endpoint para baixar o arquivo ZIP com Markdown e imagens prontos para uso.
    Após o download, limpa os arquivos temporários (MD, images/).
    """
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo comprimido não encontrado.")

    # Função de limpeza síncrona (sem async)
    def cleanup_files():
        import time
        time.sleep(0.5)  # Aguardar um pouco para garantir que o download foi enviado
        try:
            # Verificar se é ZIP consolidado (múltiplos PDFs) ou simples
            is_consolidated = filename == "consolidado_completo.zip"

            if is_consolidated:
                # Para ZIP consolidado, remover todos os .md files
                print("🧹 Limpando arquivos de múltiplos PDFs...")
                for file in os.listdir(OUTPUT_DIR):
                    if file.endswith(".md"):
                        md_path = os.path.join(OUTPUT_DIR, file)
                        if os.path.exists(md_path):
                            os.remove(md_path)
                            print(f"✅ Removido: {md_path}")
            else:
                # Para ZIP simples, remover apenas o MD correspondente
                pdf_basename = filename.replace("_completo.zip", "")
                md_path = os.path.join(OUTPUT_DIR, f"{pdf_basename}.md")
                if os.path.exists(md_path):
                    os.remove(md_path)
                    print(f"✅ Removido: {md_path}")

            # Remover pasta de imagens
            img_dir = os.path.join(OUTPUT_DIR, "images")
            if os.path.exists(img_dir):
                shutil.rmtree(img_dir)
                print(f"✅ Removido: {img_dir}")

            # Remover o próprio ZIP
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"✅ Removido: {file_path}")

        except Exception as e:
            # Log do erro mas não falha o download
            print(f"⚠️  Erro ao limpar arquivos temporários: {e}")

    # Agendar limpeza em background
    import threading
    cleanup_thread = threading.Thread(target=cleanup_files, daemon=True)
    cleanup_thread.start()

    return FileResponse(
        file_path,
        media_type="application/zip",
        filename=filename
    )

@app.get("/api/health/", summary="Health check")
def health_check():
    """
    Endpoint para verificar se o backend está rodando.
    """
    return JSONResponse({"status": "ok"})

# Serve frontend DEPOIS das rotas de API
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
