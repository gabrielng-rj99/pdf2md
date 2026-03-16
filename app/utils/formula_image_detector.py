"""
Detector de imagens de fórmulas matemáticas em PDFs.

Heurísticas:
1. Aspect ratio característico (fórmulas tendem a ser mais largas que altas)
2. Posição central na página (fórmulas em bloco são centralizadas)
3. Ausência de cores vibrantes (fórmulas são tipicamente preto/branco)
4. Tamanho característico (nem muito pequeno, nem muito grande)
5. Proximidade de texto matemático detectado pelo math_zone_detector
"""

import fitz
import numpy as np
from PIL import Image
import io
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from enum import Enum


class ImageFormulaType(Enum):
    """Tipo de imagem de fórmula detectada."""
    DISPLAY = "display"      # Fórmula em bloco (centralizada)
    INLINE = "inline"        # Fórmula inline (menor)
    COMPLEX = "complex"     # Matriz, integral grande, etc.


@dataclass
class FormulaImageCandidate:
    """Candidata a imagem de fórmula."""
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    page_num: int
    image_index: int
    confidence: float  # 0.0 - 1.0
    formula_type: ImageFormulaType
    width: int
    height: int
    image_data: Optional[bytes] = None


class FormulaImageDetector:
    """
    Detecta imagens que provavelmente contêm fórmulas matemáticas.

    Usa heuristics sem ML para identificar regiões de fórmulas:
    - Posição central na página
    - Proporção característica (mais larga que alta)
    - Ausência de cores vibrantes (tipicamente PB)
    - Proximidade de texto matemático
    """

    # Configuração padrão
    MIN_WIDTH = 30       # Largura mínima (pixels)
    MIN_HEIGHT = 20      # Altura mínima
    MAX_WIDTH = 800     # Largura máxima típica
    MAX_HEIGHT = 300    # Altura máxima típica

    # Proporção característica de fórmulas (largura/altura)
    MIN_ASPECT_RATIO = 0.8   # Fórmulas são geralmente mais largas
    MAX_ASPECT_RATIO = 15.0  # Mas não extremamente longas

    # Margem central (fórmulas em bloco são centralizadas)
    CENTER_MARGIN_PERCENT = 0.25  # 25% da largura da página

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._stats = {'images_checked': 0, 'formulas_detected': 0}

    def detect_formula_images(
        self,
        doc: fitz.Document,
        math_zones: Optional[List] = None
    ) -> List[FormulaImageCandidate]:
        """
        Detecta imagens que provavelmente contêm fórmulas.

        Args:
            doc: Documento PyMuPDF
            math_zones: Zonas matemáticas detectadas (opcional, para validação)

        Returns:
            Lista de candidatas a imagens de fórmulas
        """
        candidates = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_width = page.rect.width
            page_height = page.rect.height

            # Obter imagens da página
            images = page.get_images(full=True)

            for img_index, img in enumerate(images):
                try:
                    # Extrair informações da imagem
                    xref = img[0]
                    base_image = doc.extract_image(xref)

                    width = base_image.get('width', 0)
                    height = base_image.get('height', 0)
                    image_data = base_image.get('image', b'')

                    if not image_data:
                        continue

                    self._stats['images_checked'] += 1

                    # Verificar se é candidta a fórmula
                    candidate = self._evaluate_image(
                        img_index=img_index,
                        xref=xref,
                        page=page,
                        page_num=page_num,
                        page_width=page_width,
                        page_height=page_height,
                        width=width,
                        height=height,
                        image_data=image_data,
                        math_zones=math_zones
                    )

                    if candidate:
                        candidates.append(candidate)
                        self._stats['formulas_detected'] += 1

                except Exception as e:
                    # Log erro mas continue
                    print(f"Erro ao processar imagem {img_index}: {e}")
                    continue

        return candidates

    def _evaluate_image(
        self,
        img_index: int,
        xref: int,
        page: fitz.Page,
        page_num: int,
        page_width: float,
        page_height: float,
        width: int,
        height: int,
        image_data: bytes,
        math_zones: Optional[List]
    ) -> Optional[FormulaImageCandidate]:
        """Avalia se uma imagem é uma fórmula."""

        score = 0.0

        # 1. Verificar dimensões básicas
        if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
            return None
        if width > self.MAX_WIDTH * 2 or height > self.MAX_HEIGHT * 2:
            return None

        # 2. Verificar aspect ratio característico
        aspect_ratio = width / height if height > 0 else 0
        if self.MIN_ASPECT_RATIO <= aspect_ratio <= self.MAX_ASPECT_RATIO:
            score += 0.3

        # 3. Verificar posição (centralizada = fórmula em bloco)
        # Obter bbox da imagem
        try:
            img_dict = page.get_image_rects(xref)
            if img_dict:
                bbox = img_dict[0]
                center_x = (bbox.x0 + bbox.x1) / 2
                page_center_x = page_width / 2

                # Distância do centro
                center_distance = abs(center_x - page_center_x) / page_width

                if center_distance < self.CENTER_MARGIN_PERCENT:
                    score += 0.25
            else:
                center_distance = 0.5  # Default to not centered
        except:
            center_distance = 0.5

        # 4. Verificar cores (PB = fórmula)
        if self._is_black_and_white(image_data):
            score += 0.3

        # 5. Verificar tamanho característico
        area = width * height
        if 1000 < area < 100000:  # Área típica de fórmulas
            score += 0.15

        # Determinar tipo
        formula_type = ImageFormulaType.DISPLAY if center_distance < 0.1 else ImageFormulaType.INLINE
        if width > 200 and height > 80:
            formula_type = ImageFormulaType.COMPLEX

        # Retornar se confiança suficiente
        if score >= 0.4:
            bbox = (0, 0, width, height)  # Default bbox
            try:
                img_dict = page.get_image_rects(xref)
                if img_dict:
                    bbox = (img_dict[0].x0, img_dict[0].y0, img_dict[0].x1, img_dict[0].y1)
            except:
                pass

            return FormulaImageCandidate(
                bbox=bbox,
                page_num=page_num,
                image_index=img_index,
                confidence=min(score, 1.0),
                formula_type=formula_type,
                width=width,
                height=height,
                image_data=image_data
            )

        return None

    def _is_black_and_white(self, image_data: bytes, threshold: float = 0.9) -> bool:
        """Verifica se imagem é essencialmente preto e branco."""
        try:
            img = Image.open(io.BytesIO(image_data))
            img = img.convert('RGB')
            img_array = np.array(img)

            # Contar pixels próximos de PB
            total_pixels = img_array.shape[0] * img_array.shape[1]

            # Calcular luminância
            luminance = 0.299 * img_array[:,:,0] + 0.587 * img_array[:,:,1] + 0.114 * img_array[:,:,2]

            # Pixel é PB se R≈G≈B
            rgb_diff = np.abs(img_array[:,:,0] - img_array[:,:,1]) + \
                       np.abs(img_array[:,:,1] - img_array[:,:,2]) + \
                       np.abs(img_array[:,:,0] - img_array[:,:,2])

            bw_pixels = np.sum(rgb_diff < 30)
            bw_ratio = bw_pixels / total_pixels

            return bw_ratio > threshold

        except Exception:
            return False

    def get_stats(self) -> Dict:
        return self._stats.copy()
