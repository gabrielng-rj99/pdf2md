#!/usr/bin/env python3
"""
Script de teste para validar o processamento de múltiplos PDFs.
Testa o endpoint /api/upload-multiple/ com múltiplos arquivos.
"""

import requests
import os
import json
from pathlib import Path

# Configuração
API_BASE_URL = "http://localhost:8000"
UPLOAD_ENDPOINT = f"{API_BASE_URL}/api/upload-multiple/"
DOWNLOAD_ENDPOINT = f"{API_BASE_URL}/api/download-zip"

# Diretório de teste
TEST_DIR = Path(__file__).parent
OUTPUT_DIR = TEST_DIR.parent / "output"


def test_health_check():
    """Verifica se o servidor está rodando."""
    print("\n🔍 Verificando saúde do servidor...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/health/")
        if response.status_code == 200:
            print("✅ Servidor está rodando")
            return True
        else:
            print(f"❌ Servidor respondeu com status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Não foi possível conectar ao servidor")
        print("   Execute: python3 -m uvicorn app.main:app --reload")
        return False


def find_pdf_files():
    """Procura por arquivos PDF no diretório de teste."""
    print("\n🔍 Procurando arquivos PDF...")
    pdf_files = list(TEST_DIR.glob("*.pdf"))

    if not pdf_files:
        print("⚠️  Nenhum arquivo PDF encontrado em test_files/")
        print("   Coloque alguns PDFs em PDF-to-Markdown-with-Images/test_files/ e tente novamente")
        return []

    print(f"✅ Encontrados {len(pdf_files)} arquivo(s) PDF:")
    for pdf in pdf_files:
        size_mb = pdf.stat().st_size / (1024 * 1024)
        print(f"   - {pdf.name} ({size_mb:.2f} MB)")

    return pdf_files


def test_upload_multiple(pdf_files):
    """Testa o upload de múltiplos PDFs."""
    print(f"\n📤 Enviando {len(pdf_files)} arquivo(s) para o servidor...")

    try:
        # Preparar files para multipart upload
        files = []
        for pdf_file in pdf_files:
            files.append(('files', open(pdf_file, 'rb')))

        print(f"   Enviando {len(files)} arquivo(s)...")
        response = requests.post(UPLOAD_ENDPOINT, files=files)

        # Fechar arquivos
        for _, file_obj in files:
            file_obj.close()

        if response.status_code == 200:
            data = response.json()
            print("✅ Upload bem-sucedido!")
            print(f"   ZIP file: {data.get('zip_file')}")
            print(f"   Download URL: {data.get('download_url')}")
            return data
        else:
            print(f"❌ Upload falhou com status {response.status_code}")
            print(f"   Resposta: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Erro ao fazer upload: {e}")
        return None


def test_download_zip(zip_filename):
    """Testa o download do ZIP consolidado."""
    print(f"\n📥 Baixando ZIP: {zip_filename}...")

    try:
        download_url = f"{DOWNLOAD_ENDPOINT}/{zip_filename}"
        response = requests.get(download_url)

        if response.status_code == 200:
            # Salvar ZIP localmente para inspeção
            output_path = TEST_DIR / zip_filename
            with open(output_path, 'wb') as f:
                f.write(response.content)

            size_mb = len(response.content) / (1024 * 1024)
            print(f"✅ ZIP baixado com sucesso!")
            print(f"   Tamanho: {size_mb:.2f} MB")
            print(f"   Salvo em: {output_path}")

            # Inspecionar conteúdo do ZIP
            import zipfile
            try:
                with zipfile.ZipFile(output_path, 'r') as zipf:
                    files_in_zip = zipf.namelist()
                    print(f"\n📦 Conteúdo do ZIP ({len(files_in_zip)} arquivos):")
                    for file_name in sorted(files_in_zip):
                        file_info = zipf.getinfo(file_name)
                        print(f"   - {file_name} ({file_info.file_size} bytes)")
            except Exception as e:
                print(f"⚠️  Erro ao inspecionar ZIP: {e}")

            return True
        else:
            print(f"❌ Download falhou com status {response.status_code}")
            print(f"   Resposta: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Erro ao baixar ZIP: {e}")
        return False


def check_cleanup():
    """Verifica se os arquivos foram limpos após o download."""
    print(f"\n🧹 Verificando limpeza de arquivos...")

    import time
    time.sleep(1)  # Aguardar a limpeza em background

    if not OUTPUT_DIR.exists():
        print("✅ Diretório output/ foi removido (limpeza bem-sucedida)")
        return True

    contents = list(OUTPUT_DIR.glob("*"))
    if len(contents) == 0:
        print("✅ Diretório output/ está vazio (limpeza bem-sucedida)")
        return True
    else:
        print(f"⚠️  Diretório output/ ainda contém {len(contents)} item(s):")
        for item in contents:
            print(f"   - {item.name}")
        return False


def main():
    """Executa todos os testes."""
    print("=" * 60)
    print("🧪 TESTE DE MÚLTIPLOS PDFs")
    print("=" * 60)

    # 1. Verificar saúde do servidor
    if not test_health_check():
        return

    # 2. Procurar PDFs
    pdf_files = find_pdf_files()
    if not pdf_files:
        print("\n💡 Para testar com múltiplos PDFs:")
        print("   1. Coloque 2+ PDFs em PDF-to-Markdown-with-Images/test_files/")
        print("   2. Execute este script novamente")
        return

    # Se houver apenas 1 PDF, avisar
    if len(pdf_files) == 1:
        print("\n💡 Dica: Coloque 2+ PDFs em test_files/ para testar o consolidamento de imagens")

    # 3. Fazer upload
    response = test_upload_multiple(pdf_files)
    if not response:
        return

    zip_filename = response.get('zip_file')
    if not zip_filename:
        print("❌ ZIP filename não foi retornado na resposta")
        return

    # 4. Baixar ZIP
    if not test_download_zip(zip_filename):
        return

    # 5. Verificar limpeza
    check_cleanup()

    print("\n" + "=" * 60)
    print("✅ TESTES CONCLUÍDOS COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    main()
