"""
Módulo de detecção e formatação de listas para PDFs.

Este módulo fornece funcionalidades para detectar e formatar corretamente
listas (bullets, checklists, enumerações) que são extraídas de PDFs.

O problema principal que resolve:
- PDFs usam caracteres especiais para bullets (ex: \\uf0fc, •, ○, ■, etc.)
- PyMuPDF extrai cada item como um bloco separado
- Sem tratamento especial, os itens são concatenados em texto corrido

Uso:
    from app.utils.list_detector import ListDetector, get_list_detector

    detector = get_list_detector()

    # Verificar se um texto é item de lista
    if detector.is_list_item(text):
        formatted = detector.format_list_item(text)

    # Processar um parágrafo que pode conter lista inline
    result = detector.process_paragraph(paragraph)
"""

import re
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class ListType(Enum):
    """Tipos de lista suportados."""
    BULLET = auto()       # Lista não ordenada com bullets
    CHECKBOX = auto()     # Checklist/checkbox
    NUMBERED = auto()     # Lista numerada
    LETTERED = auto()     # Lista com letras (a, b, c ou A, B, C)
    ROMAN = auto()        # Lista com números romanos
    NONE = auto()         # Não é lista


@dataclass
class ListItem:
    """Representa um item de lista detectado."""
    text: str
    list_type: ListType
    marker: str
    level: int = 0  # Nível de indentação (0 = raiz)
    original_marker: str = ""  # Marcador original do PDF

    @property
    def markdown(self) -> str:
        """Retorna o item formatado em Markdown."""
        indent = "  " * self.level

        if self.list_type == ListType.NUMBERED:
            return f"{indent}{self.marker}. {self.text}"
        elif self.list_type == ListType.LETTERED:
            return f"{indent}{self.marker}) {self.text}"
        elif self.list_type == ListType.ROMAN:
            return f"{indent}{self.marker}. {self.text}"
        elif self.list_type == ListType.CHECKBOX:
            # Usar bullet simples em vez de checkbox vazio
            return f"{indent}- {self.text}"
        else:  # BULLET
            return f"{indent}- {self.text}"


class ListDetector:
    """
    Detecta e formata listas em texto extraído de PDFs.

    Suporta:
    - Bullets Unicode: •, ◦, ○, ●, ■, □, ▪, ▫, ‣, ⁃
    - Bullets de fontes especiais: \\uf0fc (Wingdings checkbox), \\uf0b7, etc.
    - Listas numeradas: 1), 2), 1-, 2- (NÃO "1." pois confunde com seções)
    - Listas com letras: a., b., a), b)
    - Listas com romanos: i., ii., I., II.
    - Caracteres de checklist: ☐, ☑, ☒, ✓, ✗

    NÃO detecta como lista:
    - Números de seção: "1.1", "1. 1", "2.3.4"
    - Títulos numerados: "1. Introdução – Conceitos"
    """

    # Caracteres que indicam bullet/checkbox em PDFs
    BULLET_CHARS = {
        # Bullets padrão
        '•', '◦', '○', '●', '■', '□', '▪', '▫', '‣', '⁃',
        '→', '➤', '➢', '►', '▶', '★', '☆', '✦', '✧',
        # Hífens e traços como bullets
        '-', '–', '—', '−',
        # Asterisco
        '*',
    }

    # Caracteres Unicode de fontes especiais (Wingdings, Symbol, etc.)
    SPECIAL_BULLET_CHARS = {
        '\uf0fc': 'checkbox',   # Wingdings checkmark
        '\uf0b7': 'bullet',     # Symbol bullet
        '\uf0a7': 'bullet',     # Wingdings bullet
        '\uf076': 'checkbox',   # Wingdings checkbox
        '\uf077': 'checkbox',   # Wingdings checked
        '\uf0fe': 'checkbox',   # Wingdings checkbox variant
        '\uf06e': 'bullet',     # Symbol bullet variant
        '\uf0d8': 'bullet',     # Arrow bullet
        '\u2022': 'bullet',     # Standard bullet
        '\u2023': 'bullet',     # Triangular bullet
        '\u25cf': 'bullet',     # Black circle
        '\u25cb': 'bullet',     # White circle
        '\u25a0': 'bullet',     # Black square
        '\u25a1': 'bullet',     # White square
    }

    # Caracteres de checkbox
    CHECKBOX_CHARS = {
        '☐', '☑', '☒', '✓', '✗', '✔', '✘', '□', '■',
        '\uf0fc', '\uf076', '\uf077', '\uf0fe',
    }

    # Padrão para listas numeradas: "1.", "1)", "1-"
    # NÃO inclui padrões de seção como "1.1" ou "1. 1" (com espaço)
    NUMBERED_PATTERN = re.compile(r'^(\d{1,3})[\)\-]\s+(.+)$')  # Apenas ) ou - como separador
    NUMBERED_DOT_PATTERN = re.compile(r'^(\d{1,3})\.\s+([A-Za-z].*)$')  # Com ponto, mas seguido de texto

    # Padrão para listas com letras: "a.", "a)", "A.", "A)"
    LETTERED_PATTERN = re.compile(r'^([a-zA-Z])[\.\)]\s*(.*)$')

    # Padrão para romanos: "i.", "ii.", "I.", "II."
    ROMAN_PATTERN = re.compile(r'^([ivxIVX]{1,4})[\.\)]\s*(.*)$')

    # Padrão para detectar início de bullet com caractere especial
    BULLET_START_PATTERN = re.compile(r'^[\s\uf000-\uf0ff•◦○●■□▪▫‣⁃→➤➢►▶★☆✦✧\-–—−\*]+\s*(.*)$')

    def __init__(self):
        """Inicializa o detector de listas."""
        # Compilar regex para caracteres especiais
        special_chars = ''.join(re.escape(c) for c in self.SPECIAL_BULLET_CHARS.keys())
        self._special_bullet_pattern = re.compile(f'^[{special_chars}\\s]+(.*)$')

        # Padrão para detectar lista inline separada por ponto-e-vírgula
        # Ex: "texto:   Item1;   Item2;   Item3;"
        self._inline_list_pattern = re.compile(
            r'([^:]+):\s{2,}([^;]+(?:;\s{2,}[^;]+)+;?)\s*$'
        )

        # Padrão para separar itens em lista inline
        self._inline_item_pattern = re.compile(r'\s{2,}')

    def is_list_item(self, text: str) -> bool:
        """
        Verifica se o texto é um item de lista.

        Args:
            text: Texto a verificar

        Returns:
            True se for item de lista
        """
        if not text or len(text.strip()) < 2:
            return False

        text = text.strip()

        # Verificar caracteres de bullet no início
        first_char = text[0]
        if first_char in self.BULLET_CHARS:
            return True
        if first_char in self.SPECIAL_BULLET_CHARS:
            return True
        if first_char in self.CHECKBOX_CHARS:
            return True

        # Verificar padrões de numeração (mas NÃO números de seção)
        # Primeiro verificar se NÃO é número de seção (ex: "1.1", "1. 1")
        if re.match(r'^\d+\s*\.\s*\d+', text):
            return False  # É número de seção, não lista

        if self.NUMBERED_PATTERN.match(text):
            return True
        if self.NUMBERED_DOT_PATTERN.match(text):
            # Só é lista se não começar com letra maiúscula seguida de mais texto de seção
            match = self.NUMBERED_DOT_PATTERN.match(text)
            if match and not re.match(r'^[A-Z][a-z]*\s*[-–—]', match.group(2)):
                return True
        if self.LETTERED_PATTERN.match(text):
            return True
        if self.ROMAN_PATTERN.match(text):
            return True

        # Verificar caracteres especiais Unicode de fontes
        if self._special_bullet_pattern.match(text):
            return True

        return False

    def detect_list_type(self, text: str) -> Tuple[ListType, str, str]:
        """
        Detecta o tipo de lista e extrai o marcador e conteúdo.

        Args:
            text: Texto do item

        Returns:
            Tupla (tipo, marcador_original, conteúdo_limpo)
        """
        if not text:
            return ListType.NONE, "", ""

        text = text.strip()

        # Verificar checkbox primeiro (mais específico)
        first_char = text[0]
        if first_char in self.CHECKBOX_CHARS:
            content = text[1:].strip()
            # Remover possíveis espaços extras ou separadores
            content = re.sub(r'^[\s\-–—:]+', '', content).strip()
            return ListType.CHECKBOX, first_char, content

        # Verificar caracteres especiais de fontes (Wingdings, etc.)
        if first_char in self.SPECIAL_BULLET_CHARS:
            marker_type = self.SPECIAL_BULLET_CHARS[first_char]
            content = text[1:].strip()
            content = re.sub(r'^[\s\-–—:]+', '', content).strip()
            if marker_type == 'checkbox':
                return ListType.CHECKBOX, first_char, content
            return ListType.BULLET, first_char, content

        # Verificar bullets padrão
        if first_char in self.BULLET_CHARS:
            content = text[1:].strip()
            content = re.sub(r'^[\s\-–—:]+', '', content).strip()
            return ListType.BULLET, first_char, content

        # Verificar se NÃO é número de seção antes de verificar numeração
        if re.match(r'^\d+\s*\.\s*\d+', text):
            return ListType.NONE, "", text  # É seção, não lista

        # Verificar numeração
        match = self.NUMBERED_PATTERN.match(text)
        if match:
            return ListType.NUMBERED, match.group(1), match.group(2).strip()

        # Verificar numeração com ponto
        match = self.NUMBERED_DOT_PATTERN.match(text)
        if match:
            content = match.group(2).strip()
            # Não é lista se for título de seção (ex: "1. Introdução – Conceitos")
            if not re.match(r'^[A-Z][a-z]*\s*[-–—]', content):
                return ListType.NUMBERED, match.group(1), content

        # Verificar letras
        match = self.LETTERED_PATTERN.match(text)
        if match:
            return ListType.LETTERED, match.group(1), match.group(2).strip()

        # Verificar romanos
        match = self.ROMAN_PATTERN.match(text)
        if match:
            # Validar que é realmente romano e não palavra
            roman = match.group(1).lower()
            valid_romans = {'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x'}
            if roman in valid_romans:
                return ListType.ROMAN, match.group(1), match.group(2).strip()

        # Verificar padrão especial de bullet com múltiplos caracteres
        match = self._special_bullet_pattern.match(text)
        if match:
            content = match.group(1).strip()
            original_marker = text[:len(text) - len(match.group(1))].strip()
            return ListType.BULLET, original_marker, content

        return ListType.NONE, "", text

    def format_list_item(self, text: str, level: int = 0) -> str:
        """
        Formata um item de lista como Markdown.

        Args:
            text: Texto do item
            level: Nível de indentação

        Returns:
            Item formatado em Markdown
        """
        list_type, marker, content = self.detect_list_type(text)

        if list_type == ListType.NONE:
            return text

        item = ListItem(
            text=content,
            list_type=list_type,
            marker=marker if list_type in (ListType.NUMBERED, ListType.LETTERED, ListType.ROMAN) else "-",
            level=level,
            original_marker=marker
        )

        return item.markdown

    def has_inline_list(self, text: str) -> bool:
        """
        Verifica se o texto contém uma lista inline.

        Listas inline são do tipo:
        "São áreas de atuação:   Item1;   Item2;   Item3;"

        Args:
            text: Texto a verificar

        Returns:
            True se contiver lista inline
        """
        if not text or len(text) < 20:
            return False

        # Verificar padrão: "texto:   item;   item;"
        if self._inline_list_pattern.search(text):
            return True

        # Verificar múltiplos espaços antes de ponto-e-vírgula (padrão de PDF)
        # Ex: "   Item1;   Item2;   Item3;"
        semicolons = text.count(';')
        double_space_semicolons = len(re.findall(r'\s{2,}[^;]+;', text))

        if semicolons >= 3 and double_space_semicolons >= 2:
            return True

        return False

    def extract_inline_list(self, text: str) -> Tuple[str, List[str]]:
        """
        Extrai uma lista inline do texto.

        Args:
            text: Texto contendo lista inline

        Returns:
            Tupla (texto_introdutório, lista_de_itens)
        """
        if not text:
            return "", []

        # Tentar padrão "texto:   item1;   item2;"
        match = self._inline_list_pattern.search(text)
        if match:
            intro = match.group(1).strip()
            items_text = match.group(2)

            # Separar itens por ponto-e-vírgula com espaços
            items = re.split(r';\s*', items_text)
            items = [item.strip() for item in items if item.strip()]

            return intro, items

        # Padrão alternativo: detectar por múltiplos espaços
        # Encontrar onde começa a lista (após ":" ou primeiro item)
        colon_pos = text.find(':')
        if colon_pos > 0:
            intro = text[:colon_pos].strip()
            rest = text[colon_pos + 1:].strip()

            # Separar por padrão de múltiplos espaços seguidos de texto
            # Padrão: "  Item1;  Item2;" ou similar
            items = re.split(r'\s{2,}', rest)
            items = [item.strip().rstrip(';').strip() for item in items if item.strip()]

            if len(items) >= 2:
                return intro, items

        return text, []

    def process_paragraph(self, text: str) -> str:
        """
        Processa um parágrafo e converte listas inline em formato Markdown.

        Args:
            text: Parágrafo de texto

        Returns:
            Texto processado com listas formatadas
        """
        if not text:
            return ""

        # Se for um item de lista simples, formatar diretamente
        if self.is_list_item(text):
            return self.format_list_item(text)

        # Verificar se contém lista inline
        if self.has_inline_list(text):
            intro, items = self.extract_inline_list(text)

            if items and len(items) >= 2:
                # Formatar como lista Markdown
                lines = []
                if intro:
                    lines.append(intro + ":")
                    lines.append("")  # Linha em branco antes da lista

                for item in items:
                    if item:  # Evitar itens vazios
                        lines.append(f"- {item}")

                return "\n".join(lines)

        return text

    def process_blocks(self, blocks: List[str]) -> List[str]:
        """
        Processa uma lista de blocos de texto, detectando e formatando listas.

        Args:
            blocks: Lista de blocos/parágrafos

        Returns:
            Lista de blocos processados
        """
        if not blocks:
            return []

        result = []
        in_list = False
        list_items = []

        for block in blocks:
            if not block:
                continue

            # Verificar se é item de lista
            if self.is_list_item(block):
                formatted = self.format_list_item(block)

                if not in_list:
                    # Começando nova lista
                    in_list = True
                    list_items = [formatted]
                else:
                    # Continuando lista
                    list_items.append(formatted)
            else:
                # Não é item de lista
                if in_list:
                    # Finalizar lista anterior
                    result.extend(list_items)
                    result.append("")  # Linha em branco após lista
                    list_items = []
                    in_list = False

                # Processar possível lista inline
                processed = self.process_paragraph(block)
                result.append(processed)

        # Finalizar lista pendente
        if in_list and list_items:
            result.extend(list_items)

        return result


# Singleton para o detector
_list_detector_instance: Optional[ListDetector] = None


def get_list_detector() -> ListDetector:
    """
    Retorna a instância singleton do ListDetector.

    Returns:
        Instância do ListDetector
    """
    global _list_detector_instance

    if _list_detector_instance is None:
        _list_detector_instance = ListDetector()

    return _list_detector_instance


def is_list_item(text: str) -> bool:
    """Função de conveniência para verificar se é item de lista."""
    return get_list_detector().is_list_item(text)


def format_list_item(text: str, level: int = 0) -> str:
    """Função de conveniência para formatar item de lista."""
    return get_list_detector().format_list_item(text, level)


def process_paragraph_lists(text: str) -> str:
    """Função de conveniência para processar listas em parágrafo."""
    return get_list_detector().process_paragraph(text)
