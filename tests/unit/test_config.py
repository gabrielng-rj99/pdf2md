"""
Testes para o módulo app.config e app.utils.helpers

Testa:
- Configurações do aplicativo
- Funções auxiliares (helpers)
- Validações de caminhos
- Valores padrão de configuração

NOTA: Usa pytest fixtures e monkeypatch para evitar problemas de permissão.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def temp_dir():
    """Fixture para diretório temporário."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestHelpersEnsureDir:
    """Testes para a função ensure_dir."""

    def test_ensure_dir_creates_directory(self, temp_dir):
        """Deve criar um diretório que não existe."""
        from app.utils.helpers import ensure_dir

        test_path = os.path.join(temp_dir, "new_dir")
        assert not os.path.exists(test_path)

        result = ensure_dir(test_path)

        assert os.path.exists(test_path)
        assert result == test_path

    def test_ensure_dir_returns_path(self, temp_dir):
        """Deve retornar o caminho passado."""
        from app.utils.helpers import ensure_dir

        result = ensure_dir(temp_dir)
        assert result == temp_dir

    def test_ensure_dir_existing_directory(self, temp_dir):
        """Deve funcionar com diretório que já existe."""
        from app.utils.helpers import ensure_dir

        result = ensure_dir(temp_dir)
        assert result == temp_dir
        assert os.path.exists(result)

    def test_ensure_dir_nested_creation(self, temp_dir):
        """Deve criar diretórios aninhados."""
        from app.utils.helpers import ensure_dir

        nested_path = os.path.join(temp_dir, "level1", "level2", "level3")
        result = ensure_dir(nested_path)
        assert os.path.exists(nested_path)
        assert result == nested_path

    def test_ensure_dir_returns_string(self, temp_dir):
        """Deve retornar uma string."""
        from app.utils.helpers import ensure_dir

        result = ensure_dir(temp_dir)
        assert isinstance(result, str)

    def test_ensure_dir_is_idempotent(self, temp_dir):
        """Chamar múltiplas vezes não deve gerar erro."""
        from app.utils.helpers import ensure_dir

        test_path = os.path.join(temp_dir, "test")
        ensure_dir(test_path)
        result = ensure_dir(test_path)  # Segunda chamada
        assert os.path.exists(result)


class TestHelpersGetProjectRoot:
    """Testes para a função get_project_root."""

    def test_get_project_root_returns_path(self):
        """Deve retornar um Path."""
        from app.utils.helpers import get_project_root
        root = get_project_root()
        assert isinstance(root, Path)

    def test_get_project_root_exists(self):
        """Diretório raiz deve existir."""
        from app.utils.helpers import get_project_root
        root = get_project_root()
        assert root.exists()

    def test_get_project_root_is_directory(self):
        """Deve retornar um diretório, não um arquivo."""
        from app.utils.helpers import get_project_root
        root = get_project_root()
        assert root.is_dir()

    def test_get_project_root_consistency(self):
        """Deve retornar o mesmo caminho quando chamado múltiplas vezes."""
        from app.utils.helpers import get_project_root
        root1 = get_project_root()
        root2 = get_project_root()
        assert root1 == root2


class TestHelpersGetOutputDir:
    """Testes para a função get_output_dir."""

    def test_get_output_dir_returns_string(self, monkeypatch, temp_dir):
        """Deve retornar uma string."""
        from app.utils.helpers import get_output_dir

        # Monkeypatch get_project_root para retornar temp_dir
        with patch('app.utils.helpers.get_project_root') as mock_root:
            mock_root.return_value = Path(temp_dir)
            output_dir = get_output_dir()
            assert isinstance(output_dir, str)

    def test_get_output_dir_contains_output(self, monkeypatch, temp_dir):
        """Deve conter 'output' no nome."""
        from app.utils.helpers import get_output_dir

        with patch('app.utils.helpers.get_project_root') as mock_root:
            mock_root.return_value = Path(temp_dir)
            output_dir = get_output_dir()
            assert "output" in output_dir.lower()

    def test_get_output_dir_consistency(self, monkeypatch, temp_dir):
        """Deve retornar o mesmo caminho quando chamado múltiplas vezes."""
        from app.utils.helpers import get_output_dir

        with patch('app.utils.helpers.get_project_root') as mock_root:
            mock_root.return_value = Path(temp_dir)
            dir1 = get_output_dir()
            dir2 = get_output_dir()
            assert dir1 == dir2


class TestHelpersGetImagesDir:
    """Testes para a função get_images_dir."""

    def test_get_images_dir_returns_string(self, monkeypatch, temp_dir):
        """Deve retornar uma string."""
        from app.utils.helpers import get_images_dir

        with patch('app.utils.helpers.get_output_dir') as mock_output:
            mock_output.return_value = os.path.join(temp_dir, "output")
            images_dir = get_images_dir()
            assert isinstance(images_dir, str)

    def test_get_images_dir_contains_images(self, monkeypatch, temp_dir):
        """Deve conter 'images' no nome."""
        from app.utils.helpers import get_images_dir

        with patch('app.utils.helpers.get_output_dir') as mock_output:
            mock_output.return_value = os.path.join(temp_dir, "output")
            images_dir = get_images_dir()
            assert "images" in images_dir.lower()

    def test_get_images_dir_consistency(self, monkeypatch, temp_dir):
        """Deve retornar o mesmo caminho quando chamado múltiplas vezes."""
        from app.utils.helpers import get_images_dir

        with patch('app.utils.helpers.get_output_dir') as mock_output:
            mock_output.return_value = os.path.join(temp_dir, "output")
            dir1 = get_images_dir()
            dir2 = get_images_dir()
            assert dir1 == dir2


class TestHelpersSanitizeFilename:
    """Testes para a função sanitize_filename."""

    def test_sanitize_removes_angle_brackets(self):
        """Deve remover < e >."""
        from app.utils.helpers import sanitize_filename
        filename = 'file<name>.pdf'
        result = sanitize_filename(filename)
        assert '<' not in result
        assert '>' not in result

    def test_sanitize_removes_colon(self):
        """Deve remover ':'."""
        from app.utils.helpers import sanitize_filename
        filename = 'file:name.pdf'
        result = sanitize_filename(filename)
        assert ':' not in result

    def test_sanitize_removes_quotes(self):
        """Deve remover aspas duplas."""
        from app.utils.helpers import sanitize_filename
        filename = 'file"name.pdf'
        result = sanitize_filename(filename)
        assert '"' not in result

    def test_sanitize_removes_backslash(self):
        """Deve remover barras invertidas."""
        from app.utils.helpers import sanitize_filename
        filename = 'file\\name.pdf'
        result = sanitize_filename(filename)
        assert '\\' not in result

    def test_sanitize_removes_pipe(self):
        """Deve remover pipes."""
        from app.utils.helpers import sanitize_filename
        filename = 'file|name.pdf'
        result = sanitize_filename(filename)
        assert '|' not in result

    def test_sanitize_removes_question_mark(self):
        """Deve remover interrogações."""
        from app.utils.helpers import sanitize_filename
        filename = 'file?name.pdf'
        result = sanitize_filename(filename)
        assert '?' not in result

    def test_sanitize_removes_asterisk(self):
        """Deve remover asteriscos."""
        from app.utils.helpers import sanitize_filename
        filename = 'file*name.pdf'
        result = sanitize_filename(filename)
        assert '*' not in result

    def test_sanitize_preserves_alphanumeric(self):
        """Deve preservar letras e números."""
        from app.utils.helpers import sanitize_filename
        filename = 'file123name.pdf'
        result = sanitize_filename(filename)
        assert 'file123name' in result

    def test_sanitize_preserves_dots(self):
        """Deve preservar pontos."""
        from app.utils.helpers import sanitize_filename
        filename = 'file.name.pdf'
        result = sanitize_filename(filename)
        assert result.count('.') >= 1

    def test_sanitize_preserves_dashes(self):
        """Deve preservar hífens."""
        from app.utils.helpers import sanitize_filename
        filename = 'file-name.pdf'
        result = sanitize_filename(filename)
        assert '-' in result

    def test_sanitize_preserves_underscores(self):
        """Deve preservar underscores."""
        from app.utils.helpers import sanitize_filename
        filename = 'file_name.pdf'
        result = sanitize_filename(filename)
        assert '_' in result or 'file_name' in result

    def test_sanitize_empty_string(self):
        """Deve lidar com string vazia."""
        from app.utils.helpers import sanitize_filename
        result = sanitize_filename('')
        assert result == ''

    def test_sanitize_spaces(self):
        """Deve preservar espaços."""
        from app.utils.helpers import sanitize_filename
        filename = 'file name.pdf'
        result = sanitize_filename(filename)
        assert 'file' in result and 'name' in result

    def test_sanitize_unicode(self):
        """Deve preservar caracteres Unicode válidos."""
        from app.utils.helpers import sanitize_filename
        filename = 'documento_português.pdf'
        result = sanitize_filename(filename)
        # Não deve quebrar com Unicode
        assert len(result) > 0

    def test_sanitize_all_invalid_chars(self):
        """Deve remover todos os caracteres inválidos."""
        from app.utils.helpers import sanitize_filename
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            filename = f'file{char}name.pdf'
            result = sanitize_filename(filename)
            assert char not in result

    def test_sanitize_maintains_length_approximate(self):
        """Tamanho do resultado deve ser aproximado ao original."""
        from app.utils.helpers import sanitize_filename
        filename = 'file<name>test.pdf'
        result = sanitize_filename(filename)
        # Cada char inválido vira underscore, então tamanho deve ser similar
        assert len(result) == len(filename)

    def test_sanitize_returns_string(self):
        """Deve retornar uma string."""
        from app.utils.helpers import sanitize_filename
        result = sanitize_filename('test.pdf')
        assert isinstance(result, str)


class TestHelpersIntegration:
    """Testes de integração dos helpers."""

    def test_all_helper_functions_exist(self):
        """Todos os helpers necessários devem ser acessíveis."""
        from app.utils import helpers

        functions = [
            'ensure_dir',
            'get_project_root',
            'get_output_dir',
            'get_images_dir',
            'sanitize_filename',
        ]
        for func_name in functions:
            assert hasattr(helpers, func_name)
            assert callable(getattr(helpers, func_name))

    def test_helpers_basic_workflow(self, temp_dir):
        """Helpers devem funcionar bem juntos em um fluxo básico."""
        from app.utils.helpers import (
            sanitize_filename,
            ensure_dir,
        )

        # Sanitize a filename
        unsafe_name = 'test<file>name.pdf'
        safe_name = sanitize_filename(unsafe_name)
        assert '<' not in safe_name

        # Create a directory with safe name
        full_path = os.path.join(temp_dir, safe_name)
        result = ensure_dir(full_path)
        assert os.path.exists(result)

    def test_get_project_root_valid_path(self):
        """get_project_root deve retornar um caminho válido."""
        from app.utils.helpers import get_project_root

        root = get_project_root()
        assert root.exists()
        assert root.is_dir()
        # Deve conter um arquivo app.py ou pasta app
        assert (root / "app").exists() or (root / "app.py").exists()

    def test_multiple_calls_consistency(self, temp_dir):
        """Múltiplas chamadas devem retornar resultados consistentes."""
        from app.utils.helpers import get_project_root, sanitize_filename

        root1 = get_project_root()
        root2 = get_project_root()
        assert root1 == root2

        safe1 = sanitize_filename('test<file>.pdf')
        safe2 = sanitize_filename('test<file>.pdf')
        assert safe1 == safe2


class TestConfigModuleStructure:
    """Testes para a estrutura do módulo config."""

    def test_config_file_exists(self):
        """Arquivo config.py deve existir."""
        config_path = Path(__file__).parent.parent.parent / "app" / "config.py"
        assert config_path.exists()

    def test_config_file_is_readable(self):
        """Arquivo config.py deve ser legível."""
        config_path = Path(__file__).parent.parent.parent / "app" / "config.py"
        with open(config_path) as f:
            content = f.read()
            assert len(content) > 0

    def test_config_has_required_constants(self):
        """Config deve definir constantes obrigatórias."""
        config_path = Path(__file__).parent.parent.parent / "app" / "config.py"
        with open(config_path) as f:
            content = f.read()

            required = [
                'BASE_DIR',
                'OUTPUT_DIR',
                'FRONTEND_DIR',
                'DEBUG',
                'API_TITLE',
                'API_DESCRIPTION',
                'API_VERSION',
                'MAX_UPLOAD_SIZE',
                'ALLOWED_EXTENSIONS',
                'IMAGES_DIR',
            ]
            for const in required:
                assert const in content, f"Config missing constant: {const}"

    def test_config_valid_python(self):
        """Arquivo config.py deve ser Python válido."""
        import ast
        config_path = Path(__file__).parent.parent.parent / "app" / "config.py"
        with open(config_path) as f:
            content = f.read()
            # Deve fazer parse sem erros
            ast.parse(content)


class TestConfigImportability:
    """Testes para importabilidade da configuração."""

    def test_config_can_be_imported(self, monkeypatch, temp_dir):
        """Módulo config deve ser importável."""
        # Monkeypatch para evitar criar diretórios reais
        monkeypatch.setenv('HOME', temp_dir)

        try:
            from app import config
            assert hasattr(config, 'BASE_DIR')
            assert hasattr(config, 'OUTPUT_DIR')
            assert hasattr(config, 'DEBUG')
        except PermissionError:
            # Se houver erro de permissão, skip este teste
            pytest.skip("Permission denied on output directory")

    def test_config_constants_are_valid(self, monkeypatch, temp_dir):
        """Constantes de config devem ter valores válidos."""
        monkeypatch.setenv('HOME', temp_dir)

        try:
            from app.config import (
                BASE_DIR,
                DEBUG,
                API_TITLE,
                API_DESCRIPTION,
                API_VERSION,
                MAX_UPLOAD_SIZE,
                ALLOWED_EXTENSIONS,
            )

            # Validações básicas
            assert isinstance(BASE_DIR, Path)
            assert isinstance(DEBUG, bool)
            assert isinstance(API_TITLE, str)
            assert len(API_TITLE) > 0
            assert isinstance(API_DESCRIPTION, str)
            assert len(API_DESCRIPTION) > 0
            assert isinstance(API_VERSION, str)
            assert len(API_VERSION) > 0
            assert isinstance(MAX_UPLOAD_SIZE, int)
            assert MAX_UPLOAD_SIZE > 0
            assert isinstance(ALLOWED_EXTENSIONS, set)
            assert ".pdf" in ALLOWED_EXTENSIONS
        except PermissionError:
            pytest.skip("Permission denied on output directory")
