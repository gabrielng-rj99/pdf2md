import re
from typing import List, Dict, Tuple
import fitz


class ImageFilter:
    """
    Filtra imagens relevantes de PDFs, eliminando bordas, cabeçalhos e rodapés.
    Também detecta referências a figuras/tabelas no texto.
    """

    # Padrões de referência a imagens/figuras/tabelas
    REFERENCE_PATTERNS = [
        r"(?:figura|fig\.?)\s+(\d+)",
        r"(?:tabela|tab\.?)\s+(\d+)",
        r"(?:imagem|img\.?)\s+(\d+)",
        r"(?:gráfico|gráf\.?)\s+(\d+)",
        r"(?:chart|figure|fig\.?)\s+(\d+)",
        r"(?:table|tbl\.?)\s+(\d+)",
        r"(?:image|img\.?)\s+(\d+)",
    ]

    def __init__(self, page_height: float = 850, page_width: float = 595):
        """
        Inicializa o filtro de imagens.

        Args:
            page_height: Altura padrão da página em pontos (default A4)
            page_width: Largura padrão da página em pontos (default A4)
        """
        self.page_height = page_height
        self.page_width = page_width
        # Margens (em %) que definem bordas
        self.header_margin_percent = 0.10  # 10% do topo
        self.footer_margin_percent = 0.10  # 10% do rodapé
        self.side_margin_percent = 0.02    # 2% dos lados

    def is_header_or_footer(self, bbox: Tuple[float, float, float, float]) -> bool:
        """
        Verifica se uma imagem está no cabeçalho ou rodapé.

        Args:
            bbox: Bounding box (x0, y0, x1, y1)

        Returns:
            True se está nas bordas verticais
        """
        x0, y0, x1, y1 = bbox

        header_threshold = self.page_height * self.header_margin_percent
        footer_threshold = self.page_height * (1 - self.footer_margin_percent)

        # Imagem no topo (cabeçalho)
        if y1 <= header_threshold:
            return True

        # Imagem no rodapé
        if y0 >= footer_threshold:
            return True

        return False

    def is_side_margin(self, bbox: Tuple[float, float, float, float]) -> bool:
        """
        Verifica se uma imagem está nas margens laterais (muito pequena ou na borda).

        Args:
            bbox: Bounding box (x0, y0, x1, y1)

        Returns:
            True se está nas margens laterais
        """
        x0, y0, x1, y1 = bbox

        side_threshold = self.page_width * self.side_margin_percent
        right_threshold = self.page_width * (1 - self.side_margin_percent)

        # Imagem na margem esquerda
        if x0 < side_threshold and (x1 - x0) < 50:
            return True

        # Imagem na margem direita
        if x1 > right_threshold and (x1 - x0) < 50:
            return True

        return False

    def get_image_size(self, bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
        """
        Calcula dimensões da imagem baseado no bbox.

        Args:
            bbox: Bounding box (x0, y0, x1, y1)

        Returns:
            Tupla (largura, altura)
        """
        x0, y0, x1, y1 = bbox
        return (x1 - x0, y1 - y0)

    def is_too_small(self, bbox: Tuple[float, float, float, float], min_area: float = 3000) -> bool:
        """
        Verifica se a imagem é muito pequena para ser relevante.

        Args:
            bbox: Bounding box (x0, y0, x1, y1)
            min_area: Área mínima em pixels quadrados

        Returns:
            True se a imagem é muito pequena
        """
        width, height = self.get_image_size(bbox)
        area = width * height
        return area < min_area

    def find_figure_references(self, page_text: str) -> Dict[str, List[int]]:
        """
        Busca por referências a figuras, tabelas, etc no texto.

        Args:
            page_text: Texto da página

        Returns:
            Dicionário com tipos e números de referências encontradas
        """
        references = {}

        for pattern in self.REFERENCE_PATTERNS:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                ref_type = match.group(0).split()[0].lower()
                ref_num = int(match.group(1))

                if ref_type not in references:
                    references[ref_type] = []

                if ref_num not in references[ref_type]:
                    references[ref_type].append(ref_num)

        return references

    def is_relevant_image(
        self,
        bbox: Tuple[float, float, float, float],
        page_text: str = "",
        has_figure_reference: bool = False,
    ) -> bool:
        """
        Determina se uma imagem é relevante (não é borda, cabeçalho, etc).

        Args:
            bbox: Bounding box da imagem
            page_text: Texto da página (para detectar referências)
            has_figure_reference: Se a página tem referência a figura/tabela

        Returns:
            True se a imagem é relevante
        """
        # Filtro 1: Remover cabeçalhos e rodapés
        if self.is_header_or_footer(bbox):
            return False

        # Filtro 2: Remover margens laterais muito pequenas
        if self.is_side_margin(bbox):
            return False

        # Filtro 3: Remover imagens muito pequenas
        if self.is_too_small(bbox):
            return False

        # Filtro 4: Preferir imagens em páginas com referências a figuras
        if has_figure_reference:
            # Se tem referência a figura, é mais provável ser relevante
            return True

        # Filtro 5: Se não tem referência, mas tem tamanho significativo, é relevante
        width, height = self.get_image_size(bbox)
        if width > 100 and height > 100:
            return True

        return False

    def get_nearby_text(
        self,
        page_dict: Dict,
        image_bbox: Tuple[float, float, float, float],
        distance: float = 50,
    ) -> str:
        """
        Extrai texto próximo a uma imagem para verificar referências.

        Args:
            page_dict: Dicionário da página (do PyMuPDF)
            image_bbox: Bounding box da imagem
            distance: Distância em pontos para buscar texto

        Returns:
            Texto próximo à imagem
        """
        x0, y0, x1, y1 = image_bbox
        search_bbox = (x0 - distance, y0 - distance, x1 + distance, y1 + distance)

        nearby_text = ""
        blocks = page_dict.get("blocks", [])

        for block in blocks:
            if isinstance(block, dict) and "lines" in block:
                block_bbox = block.get("bbox", [])
                # Verificar se o bloco de texto está próximo à imagem
                if self._bboxes_overlap_or_near(search_bbox, block_bbox, distance):
                    for line in block.get("lines", []):
                        if isinstance(line, dict) and "spans" in line:
                            for span in line.get("spans", []):
                                if isinstance(span, dict):
                                    nearby_text += span.get("text", "") + " "

        return nearby_text

    @staticmethod
    def _bboxes_overlap_or_near(
        bbox1: Tuple[float, float, float, float],
        bbox2: Tuple[float, float, float, float],
        tolerance: float = 0,
    ) -> bool:
        """
        Verifica se dois bounding boxes se sobrepõem ou estão próximos.

        Args:
            bbox1: Primeiro bbox (x0, y0, x1, y1)
            bbox2: Segundo bbox (x0, y0, x1, y1)
            tolerance: Tolerância em pontos

        Returns:
            True se se sobrepõem ou estão próximos
        """
        x0_1, y0_1, x1_1, y1_1 = bbox1
        x0_2, y0_2, x1_2, y1_2 = bbox2

        return not (
            x1_1 + tolerance < x0_2
            or x0_1 - tolerance > x1_2
            or y1_1 + tolerance < y0_2
            or y0_1 - tolerance > y1_2
        )
