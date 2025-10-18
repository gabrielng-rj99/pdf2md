import os
from pathlib import Path


def ensure_dir(path: str) -> str:
    """Cria um diretório se não existir e retorna o caminho."""
    os.makedirs(path, exist_ok=True)
    return path


def get_project_root() -> Path:
    """Retorna o caminho raiz do projeto."""
    return Path(__file__).parent.parent.parent


def get_output_dir() -> str:
    """Retorna o caminho da pasta de output."""
    output_path = os.path.join(get_project_root(), "output")
    return ensure_dir(output_path)


def get_images_dir() -> str:
    """Retorna o caminho da pasta de imagens dentro de output."""
    images_path = os.path.join(get_output_dir(), "images")
    return ensure_dir(images_path)


def sanitize_filename(filename: str) -> str:
    """Remove caracteres inválidos do nome do arquivo."""
    invalid_chars = r'<>:"/\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")
    return filename
