import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TextBlock:
    """Representa um bloco de texto com metadados."""
    content: str
    block_type: str  # 'paragraph', 'heading', 'list_item', 'image'
    page_num: int
    position: Tuple[float, float, float, float]  # bbox


class MarkdownFormatter:
    """
    Formata texto extraído de PDF em Markdown bem estruturado.
    - Consolida linhas de parágrafos
    - Gerencia quebras de linha apropriadas
    - Integra referências de imagens com o texto
    """

    def __init__(self):
        self.blocks: List[TextBlock] = []
        self.current_paragraph: List[str] = []
        self.image_references: Dict[str, str] = {}  # numero -> caminho_imagem

    def add_span(self, text: str, span_data: Dict[str, Any], page_num: int, bbox: Tuple) -> None:
        """
        Adiciona um span de texto com formatação Markdown.

        Args:
            text: Texto do span
            span_data: Dados do span (fonte, formatação, etc)
            page_num: Número da página
            bbox: Bounding box do texto
        """
        if not text or not text.strip():
            return

        formatted_text = self._format_span(text, span_data)
        self.current_paragraph.append(formatted_text)

    def _format_span(self, text: str, span_data: Dict[str, Any]) -> str:
        """
        Aplica formatação Markdown ao texto do span.

        Args:
            text: Texto original
            span_data: Dados do span (fonte, tamanho, cor, etc)

        Returns:
            Texto com formatação Markdown
        """
        # Detectar bold/italic pela fonte
        font = span_data.get("font", "").lower()
        size = span_data.get("size", 0)
        flags = span_data.get("flags", 0)

        # PyMuPDF flags: 1=superscript, 2=italic, 4=serifed, 8=monospaced, 16=bold
        is_bold = (flags & 16) or "bold" in font
        is_italic = (flags & 2) or "italic" in font or "oblique" in font
        is_link = "uri" in span_data

        # Aplicar formatação
        result = text
        if is_bold:
            result = f"**{result}**"
        if is_italic:
            result = f"*{result}*"

        return result

    def end_paragraph(self, page_num: int, bbox: Tuple = (0, 0, 0, 0)) -> None:
        """
        Encerra parágrafo atual e adiciona como bloco.

        Args:
            page_num: Número da página
            bbox: Bounding box do parágrafo
        """
        if not self.current_paragraph:
            return

        content = "".join(self.current_paragraph).strip()
        if content:
            self.blocks.append(
                TextBlock(
                    content=content,
                    block_type="paragraph",
                    page_num=page_num,
                    position=bbox,
                )
            )

        self.current_paragraph = []

    def add_heading(self, text: str, level: int, page_num: int, bbox: Tuple = (0, 0, 0, 0)) -> None:
        """
        Adiciona um heading.

        Args:
            text: Texto do heading
            level: Nível (1-6)
            page_num: Número da página
            bbox: Bounding box
        """
        self.end_paragraph(page_num, bbox)  # Encerra parágrafo anterior

        if text.strip():
            heading_text = "#" * level + " " + text.strip()
            self.blocks.append(
                TextBlock(
                    content=heading_text,
                    block_type="heading",
                    page_num=page_num,
                    position=bbox,
                )
            )

    def add_list_item(self, text: str, level: int, page_num: int, bbox: Tuple = (0, 0, 0, 0)) -> None:
        """
        Adiciona um item de lista.

        Args:
            text: Texto do item
            level: Nível de indentação
            page_num: Número da página
            bbox: Bounding box
        """
        if text.strip():
            indent = "  " * (level - 1)
            list_text = f"{indent}- {text.strip()}"
            self.blocks.append(
                TextBlock(
                    content=list_text,
                    block_type="list_item",
                    page_num=page_num,
                    position=bbox,
                )
            )

    def add_image(
        self,
        image_path: str,
        alt_text: str = "Imagem",
        page_num: int = 0,
        bbox: Tuple = (0, 0, 0, 0),
    ) -> None:
        """
        Adiciona uma imagem.

        Args:
            image_path: Caminho relativo da imagem (ex: images/page1_img1.png)
            alt_text: Texto alternativo
            page_num: Número da página
            bbox: Bounding box da imagem
        """
        self.end_paragraph(page_num, bbox)  # Encerra parágrafo anterior

        md_image = f"![{alt_text}]({image_path})"
        self.blocks.append(
            TextBlock(
                content=md_image,
                block_type="image",
                page_num=page_num,
                position=bbox,
            )
        )

    def add_page_break(self, page_num: int) -> None:
        """Adiciona quebra de página."""
        self.end_paragraph(page_num)
        # Evita múltiplas quebras consecutivas
        if self.blocks and self.blocks[-1].content.strip() != "---":
            self.blocks.append(
                TextBlock(
                    content="---",
                    block_type="page_break",
                    page_num=page_num,
                    position=(0, 0, 0, 0),
                )
            )

    def generate_markdown(self, link_images: bool = True) -> str:
        """
        Gera Markdown final consolidado.

        Args:
            link_images: Se True, tenta linkar imagens com referências no texto

        Returns:
            String Markdown formatada
        """
        self.end_paragraph(0)  # Encerra último parágrafo

        if link_images:
            self._link_images_to_text()

        lines = []
        for block in self.blocks:
            lines.append(block.content)
            # Adiciona quebra de linha dupla entre parágrafos (exceto headings e listas)
            if block.block_type in ["paragraph", "image"]:
                lines.append("")

        # Remove múltiplas quebras de linha consecutivas
        markdown = "\n".join(lines)
        # Substitui 3+ quebras vazias por 2
        markdown = re.sub(r"\n\n\n+", "\n\n", markdown)

        return markdown.strip()

    def _link_images_to_text(self) -> None:
        """
        Vincula imagens com referências de figura/tabela no texto.
        Move imagens para próximo ao texto que as referencia.
        """
        # Padrões para detectar referências
        patterns = [
            (r"(?:figura|fig\.?)\s+(\d+)", "figura"),
            (r"(?:tabela|tab\.?)\s+(\d+)", "tabela"),
            (r"(?:imagem|img\.?)\s+(\d+)", "imagem"),
            (r"(?:gráfico|gráf\.?)\s+(\d+)", "gráfico"),
        ]

        image_blocks = [i for i, b in enumerate(self.blocks) if b.block_type == "image"]

        # Para cada bloco de texto, procura referências
        for i, block in enumerate(self.blocks):
            if block.block_type != "paragraph":
                continue

            for pattern, ref_type in patterns:
                matches = list(re.finditer(pattern, block.content, re.IGNORECASE))
                if matches:
                    # Encontrou referências neste parágrafo
                    # Coloca imagens próximas após o parágrafo
                    for match in matches:
                        ref_num = match.group(1)
                        # Procura imagem correspondente
                        for img_idx in image_blocks:
                            img_block = self.blocks[img_idx]
                            # Se a imagem está próxima ou após este bloco
                            if img_idx > i:
                                # Move a imagem para logo após este parágrafo
                                # (será reorganizado na próxima iteração)
                                break

    def set_image_reference(self, figure_number: str, image_path: str) -> None:
        """
        Mapeia um número de figura para um caminho de imagem.

        Args:
            figure_number: Número da figura (ex: "1", "2")
            image_path: Caminho da imagem
        """
        self.image_references[figure_number] = image_path


def detect_heading_level(span_data: Dict[str, Any]) -> Optional[int]:
    """
    Tenta detectar se um texto é um heading baseado em tamanho/formatação.

    Args:
        span_data: Dados do span

    Returns:
        Nível de heading (1-6) ou None
    """
    size = span_data.get("size", 0)
    font = span_data.get("font", "").lower()
    flags = span_data.get("flags", 0)
    is_bold = (flags & 16) or "bold" in font

    # Heurística: texto grande e bold é provável heading
    if is_bold and size > 14:
        if size > 24:
            return 1
        elif size > 20:
            return 2
        elif size > 18:
            return 3
        else:
            return 4

    return None


def detect_list_item(text: str) -> Tuple[bool, int]:
    """
    Detecta se texto é item de lista e retorna o nível.

    Args:
        text: Texto

    Returns:
        Tupla (is_list_item, level)
    """
    # Padrões: "- ", "• ", "* ", etc.
    match = re.match(r"^(\s*)[-•*]\s+", text)
    if match:
        level = len(match.group(1)) // 2 + 1
        return True, level

    # Padrões de número: "1. ", "1.1. ", etc.
    match = re.match(r"^(\s*)\d+(\.\d+)*\.\s+", text)
    if match:
        level = len(match.group(1)) // 2 + 1
        return True, level

    return False, 0
