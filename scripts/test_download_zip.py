#!/usr/bin/env python3
"""
Script para testar o download de ZIP funciona corretamente.
"""

import os
import zipfile
import time
from fastapi.testclient import TestClient
from app.main import app
from app.services.pdf2md_service import process_pdf

def test_download_zip():
    """Testa o endpoint de download do ZIP"""
    
    client = TestClient(app)
    
    print("="*70)
    print("🧪 TESTE DE DOWNLOAD ZIP")
    print("="*70)
    
    # 1. Limpar output
    print("\n1️⃣  Limpando output/...")
    import shutil
    if os.path.exists('output/images'):
        shutil.rmtree('output/images')
    for f in os.listdir('output'):
        if f != '.gitkeep' and f != 'aula1.pdf':
            try:
                os.remove(os.path.join('output', f))
            except:
                pass
    print("   ✅ Output limpo")
    
    # 2. Processar PDF
    print("\n2️⃣  Processando PDF...")
    md_file, img_dir = process_pdf('aula1.pdf', 'output')
    print("   ✅ PDF processado")
    
    # 3. Verificar ZIP criado
    print("\n3️⃣  Verificando ZIP criado...")
    zip_path = 'output/aula1_completo.zip'
    if os.path.exists(zip_path):
        size = os.path.getsize(zip_path) / 1024
        print(f"   ✅ ZIP existe: {size:.1f} KB")
    else:
        print(f"   ❌ ZIP não existe!")
        return False
    
    # 4. Testar endpoint
    print("\n4️⃣  Testando endpoint /api/download-zip/...")
    response = client.get('/api/download-zip/aula1_completo.zip')
    
    if response.status_code == 200:
        print(f"   ✅ Status 200 OK")
        print(f"   ✅ Tamanho retornado: {len(response.content)} bytes")
        print(f"   ✅ Content-Type: {response.headers.get('content-type')}")
    else:
        print(f"   ❌ Erro {response.status_code}: {response.text}")
        return False
    
    # 5. Verificar conteúdo do ZIP
    print("\n5️⃣  Verificando conteúdo do ZIP...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        files = zf.namelist()
        print(f"   ✅ Arquivos no ZIP:")
        for f in sorted(files):
            print(f"      - {f}")
        
        # Verificar que tem MD e imagens
        has_md = any(f.endswith('.md') for f in files)
        has_images = any(f.startswith('images/') for f in files)
        
        if has_md and has_images:
            print(f"   ✅ Contém Markdown e imagens!")
        else:
            print(f"   ❌ Falta Markdown ou imagens!")
            return False
    
    # 6. Aguardar limpeza
    print("\n6️⃣  Aguardando limpeza automática (2 segundos)...")
    time.sleep(2)
    
    # 7. Verificar que foi limpo
    print("\n7️⃣  Verificando se foi limpo...")
    if not os.path.exists(zip_path):
        print(f"   ✅ ZIP removido automaticamente!")
    else:
        print(f"   ⚠️  ZIP ainda existe (pode ter tido erro na limpeza)")
    
    if not os.path.exists('output/images'):
        print(f"   ✅ Pasta images/ removida automaticamente!")
    else:
        print(f"   ⚠️  Pasta images/ ainda existe")
    
    # Resultado final
    print("\n" + "="*70)
    print("✅ TESTE COMPLETO COM SUCESSO!")
    print("="*70)
    return True

if __name__ == "__main__":
    success = test_download_zip()
    exit(0 if success else 1)

