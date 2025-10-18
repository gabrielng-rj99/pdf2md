"""
Tests package for PDF-to-Markdown-with-Images

Estrutura:
- unit/: Testes unitários para funções individuais
- integration/: Testes de integração para múltiplos componentes
- e2e/: Testes end-to-end do fluxo completo
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
