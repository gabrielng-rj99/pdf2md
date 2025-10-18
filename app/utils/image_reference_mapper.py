import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ImageReference:
    """Representa uma referência a figura/tabela/imagem no texto."""
    ref_type: str  # 'figura', 'tabela', 'imagem', 'gráfico'
    ref_number: int
    position: int  # Posição no texto
    text_snippet: str  # Trecho de texto contendo a referência


class ImageReferenceMapper:
    """
    Mapeia imagens extraídas com referências de figura/tabela no texto.
    Permite inserir imagens no local correto do Markdown.
    """

    # Padrões para detectar referências (português e inglês)
    REFERENCE_PATTERNS = [
        (r"(?:figura|fig\.?)\s+(\d+)", "figura"),
        (r"(?:tabela|tab\.?)\s+(\d+)", "tabela"),
        (r"(?:imagem|img\.?)\s+(\d+)", "imagem"),
        (r"(?:gráfico|gráf\.?)\s+(\d+)", "gráfico"),
        (r"(?:figure|fig\.?)\s+(\d+)", "figure"),
        (r"(?:table|tbl\.?)\s+(\d+)", "table"),
        (r"(?:image|img\.?)\s+(\d+)", "image"),
        (r"(?:chart|graph)\s+(\d+)", "chart"),
    ]

    def __init__(self):
        """Inicializa o mapeador de referências."""
        self.references: List[ImageReference] = []
        self.image_map: Dict[Tuple[str, int], str] = {}  # (tipo, numero) -> caminho_imagem
        self.page_images: Dict[int, List[str]] = {}  # page_num -> lista_imagens

    def add_image(self, page_num: int, image_path: str) -> None:
        """
        Registra uma imagem extraída de uma página.

        Args:
            page_num: Número da página
            image_path: Caminho relativo da imagem (ex: images/page1_img1.png)
        """
        if page_num not in self.page_images:
            self.page_images[page_num] = []
        self.page_images[page_num].append(image_path)

    def find_references_in_text(self, text: str, page_num: int = 0) -> List[ImageReference]:
        """
        Encontra todas as referências a figuras/tabelas no texto.

        Args:
            text: Texto a analisar
            page_num: Número da página (opcional)

        Returns:
            Lista de referências encontradas
        """
        references = []

        for pattern, ref_type in self.REFERENCE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                ref_num = int(match.group(1))
                position = match.start()

                # Extrair snippet de contexto
                start_snippet = max(0, position - 50)
                end_snippet = min(len(text), position + len(match.group(0)) + 50)
                snippet = text[start_snippet:end_snippet]

                ref = ImageReference(
                    ref_type=ref_type.lower(),
                    ref_number=ref_num,
                    position=position,
                    text_snippet=snippet,
                )
                references.append(ref)
                self.references.append(ref)

        return references

    def map_image_to_reference(
        self, ref_type: str, ref_number: int, image_path: str
    ) -> None:
        """
        Mapeia uma imagem para uma referência específica.

        Args:
            ref_type: Tipo de referência (figura, tabela, etc)
            ref_number: Número da referência
            image_path: Caminho da imagem
        """
        key = (ref_type.lower(), ref_number)
        self.image_map[key] = image_path

    def get_image_for_reference(self, ref_type: str, ref_number: int) -> Optional[str]:
        """
        Obtém o caminho da imagem para uma referência.

        Args:
            ref_type: Tipo de referência
            ref_number: Número da referência

        Returns:
            Caminho da imagem ou None
        """
        key = (ref_type.lower(), ref_number)
        return self.image_map.get(key)

    def get_next_available_image(self, page_num: int, exclude_used: bool = True) -> Optional[str]:
        """
        Obtém a próxima imagem disponível de uma página.

        Args:
            page_num: Número da página
            exclude_used: Se True, exclui imagens já mapeadas

        Returns:
            Caminho da imagem ou None
        """
        if page_num not in self.page_images:
            return None

        images = self.page_images[page_num]
        if not images:
            return None

        # Retorna a primeira imagem não mapeada
        if exclude_used:
            used_images = set(self.image_map.values())
            for img in images:
                if img not in used_images:
                    return img
        else:
            return images[0] if images else None

        return None

    def inject_images_into_text(self, text: str, page_num: int = 0) -> str:
        """
        Injeta referências de imagens no texto logo após as referências.

        Args:
            text: Texto original
            page_num: Número da página

        Returns:
            Texto com imagens injetadas
        """
        # Encontrar referências no texto
        references = self.find_references_in_text(text, page_num)

        if not references:
            return text

        # Ordenar referências por posição (do fim para o começo para não quebrar índices)
        references.sort(key=lambda r: r.position, reverse=True)

        result = text
        for ref in references:
            image_path = self.get_image_for_reference(ref.ref_type, ref.ref_number)

            if image_path:
                # Encontrar o fim da sentença ou parágrafo após a referência
                pos = ref.position + len(f"{ref.ref_type} {ref.ref_number}")
                # Procura próximo ponto, quebra de linha ou fim do texto
                end_match = re.search(r"[.\n]", result[pos:])
                if end_match:
                    insert_pos = pos + end_match.end()
                else:
                    insert_pos = pos

                # Inserir imagem
                image_markdown = f"\n\n![{ref.ref_type.capitalize()} {ref.ref_number}]({image_path})\n"
                result = result[:insert_pos] + image_markdown + result[insert_pos:]

        return result

    def auto_assign_images_to_references(self, page_num: int) -> Dict[Tuple[str, int], str]:
        """
        Atribui automaticamente imagens extraídas a referências encontradas.
        Usa ordem de aparição no texto.

        Args:
            page_num: Número da página

        Returns:
            Dicionário mapeado de referências para imagens
        """
        # Agrupar referências por tipo e número
        ref_by_type = {}
        for ref in self.references:
            key = (ref.ref_type, ref.ref_number)
            if key not in ref_by_type:
                ref_by_type[key] = []
            ref_by_type[key].append(ref)

        # Obter imagens da página
        images = self.page_images.get(page_num, [])

        # Atribuir imagens às referências em ordem
        image_idx = 0
        for (ref_type, ref_num), refs in sorted(ref_by_type.items()):
            if image_idx < len(images):
                self.map_image_to_reference(ref_type, ref_num, images[image_idx])
                image_idx += 1

        return self.image_map

    def get_statistics(self) -> Dict[str, int]:
        """
        Retorna estatísticas sobre referências e imagens.

        Returns:
            Dicionário com estatísticas
        """
        total_refs = len(self.references)
        total_images = sum(len(imgs) for imgs in self.page_images.values())
        mapped_images = len(self.image_map)

        return {
            "total_references": total_refs,
            "total_images_extracted": total_images,
            "images_mapped": mapped_images,
            "unmapped_references": total_refs - mapped_images,
        }

    def reset(self) -> None:
        """Reseta o mapeador."""
        self.references = []
        self.image_map = {}
        self.page_images = {}
