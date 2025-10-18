import os
from pathlib import Path

# Diretórios
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
FRONTEND_DIR = BASE_DIR / "frontend"

# Criar diretórios se não existirem
OUTPUT_DIR.mkdir(exist_ok=True)

# FastAPI
DEBUG = True
API_TITLE = "PDF2MD"
API_DESCRIPTION = "Conversor de PDF para Markdown com extração de imagens"
API_VERSION = "1.0.0"

# Upload
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".pdf"}

# Imagens
IMAGES_DIR = OUTPUT_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)
