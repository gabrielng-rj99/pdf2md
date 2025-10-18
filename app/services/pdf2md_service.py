import os
import re
import zipfile
from typing import List, Tuple, Dict
import fitz
from app.utils.image_filter import ImageFilter
from app.utils.image_reference_mapper import ImageReferenceMapper
import logging
import hashlib

logger = logging.getLogger(__name__)


def calculate_image_hash(image_path: str) -> str:
    """
    Calcula o hash MD5 de uma imagem para detectar duplicatas.

    Args:
        image_path: Caminho da imagem

    Returns:
        Hash MD5 da imagem
    """
    try:
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.warning(f"Erro ao calcular hash de {image_path}: {e}")
        return ""


def extract_images_from_page(
    doc: fitz.Document,
    page: fitz.Page,
    page_num: int,
    output_dir: str,
    pdf_name: str,
) -> List[str]:
    """
    Extrai TODAS as imagens de uma página do PDF sem filtros.

    Args:
        doc: Documento PyMuPDF
        page: Página atual
        page_num: Número da página
        output_dir: Diretório para salvar imagens
        pdf_name: Nome do arquivo PDF (para prefixo)

    Returns:
        Lista de caminhos relativos das imagens extraídas
    """
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    image_paths = []
    image_count = 0

    # Extrair todas as imagens da página
    try:
        images = page.get_images(full=False)
        logger.debug(f"Page {page_num}: Found {len(images)} images")

        for img_index, img_ref in enumerate(images):
            try:
                xref = img_ref[0]

                # Extrair imagem usando Pixmap
                pix = fitz.Pixmap(doc, xref)

                # Converter CMYK para RGB se necessário
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                image_count += 1

                # Detectar formato
                ext = "png"
                try:
                    img_data = pix.tobytes()
                    if img_data.startswith(b"\x89PNG"):
                        ext = "png"
                    elif img_data.startswith(b"\xff\xd8\xff"):
                        ext = "jpg"
                    elif img_data.startswith(b"GIF"):
                        ext = "gif"
                except Exception:
                    pass

                # Salvar imagem com prefixo do nome do arquivo
                img_filename = f"{pdf_name}_pag{page_num}_img{image_count}.{ext}"
                img_path = os.path.join(img_dir, img_filename)

                pix.save(img_path)

                rel_path = f"images/{img_filename}"
                image_paths.append(rel_path)

                logger.debug(f"Page {page_num}: Saved image {img_filename}")

            except Exception as e:
                logger.warning(f"Page {page_num}: Failed to extract image {img_index}: {e}")
                continue

    except Exception as e:
        logger.warning(f"Page {page_num}: Error in get_images(): {e}")

    return image_paths


def extract_text_blocks_from_page(page: fitz.Page, page_num: int) -> List[Dict]:
    """
    Extrai blocos de texto estruturados de uma página.

    Args:
        page: Página PyMuPDF
        page_num: Número da página

    Returns:
        Lista de blocos de texto com metadados
    """
    blocks = []

    try:
        text_dict = page.get_text("dict")

        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Bloco de texto
                for line in block.get("lines", []):
                    line_text = ""
                    font_size = 12
                    font_flags = 0

                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                        font_size = max(font_size, span.get("size", 12))
                        font_flags |= span.get("flags", 0)

                    if line_text.strip():
                        blocks.append({
                            "text": line_text,
                            "font_size": font_size,
                            "font_flags": font_flags,
                            "bbox": line.get("bbox", []),
                            "page": page_num,
                        })

    except Exception as e:
        logger.warning(f"Page {page_num}: Error extracting text blocks: {e}")

    return blocks


def consolidate_text_blocks(blocks: List[Dict]) -> List[str]:
    """
    Consolida blocos de texto em parágrafos bem formatados.

    Args:
        blocks: Lista de blocos de texto

    Returns:
        Lista de parágrafos formatados em Markdown
    """
    if not blocks:
        return []

    paragraphs = []
    current_paragraph = []
    last_font_size = None
    last_is_bold = False

    for block in blocks:
        text = block["text"].strip()
        font_size = block["font_size"]
        is_bold = bool(block["font_flags"] & 2**4)  # Flag de negrito

        # Detectar título (fonte maior ou negrito)
        is_heading = font_size > 14 or (is_bold and len(text) < 100)

        # Se for título, finalizar parágrafo anterior
        if is_heading:
            if current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []

            # Adicionar título com marcação Markdown
            if font_size > 18:
                paragraphs.append(f"# {text}")
            elif font_size > 16:
                paragraphs.append(f"## {text}")
            elif font_size > 14:
                paragraphs.append(f"### {text}")
            else:
                paragraphs.append(f"**{text}**")

            last_font_size = font_size
            last_is_bold = is_bold
            continue

        # Detectar quebra de parágrafo
        should_break = False

        # Mudança significativa de fonte
        if last_font_size and abs(font_size - last_font_size) > 2:
            should_break = True

        # Linha termina com ponto e próxima começa com maiúscula
        if (current_paragraph and
            current_paragraph[-1].endswith(".") and
            text[0].isupper()):
            should_break = True

        # Lista ou item enumerado
        if re.match(r'^[\d\-•]\s', text):
            should_break = True

        if should_break and current_paragraph:
            paragraphs.append(" ".join(current_paragraph))
            current_paragraph = []

        # Adicionar texto ao parágrafo atual
        current_paragraph.append(text)
        last_font_size = font_size
        last_is_bold = is_bold

    # Adicionar último parágrafo
    if current_paragraph:
        paragraphs.append(" ".join(current_paragraph))

    return paragraphs


def _inject_images_in_paragraphs(
    paragraphs: List[str],
    page_images: List[str],
    page_num: int,
    image_mapper: ImageReferenceMapper
) -> List[str]:
    """
    Injeta referências de imagens nos parágrafos baseado em menções no texto.

    Args:
        paragraphs: Lista de parágrafos
        page_images: Lista de imagens da página
        page_num: Número da página
        image_mapper: Mapeador de referências de imagens

    Returns:
        Lista de linhas com imagens inseridas
    """
    result = []
    used_images = set()

    # Padrões de referência a imagens
    reference_patterns = [
        r"(?:figura|fig\.?)\s+(\d+)",
        r"(?:tabela|tab\.?)\s+(\d+)",
        r"(?:imagem|img\.?)\s+(\d+)",
        r"(?:gráfico|gráf\.?)\s+(\d+)",
        r"(?:chart|figure|fig\.?)\s+(\d+)",
        r"(?:table|tbl\.?)\s+(\d+)",
        r"(?:image|img\.?)\s+(\d+)",
    ]

    for para in paragraphs:
        result.append(para)

        # Buscar referências no parágrafo
        for pattern in reference_patterns:
            matches = re.finditer(pattern, para, re.IGNORECASE)
            for match in matches:
                ref_type = match.group(0).split()[0].lower()
                ref_num = int(match.group(1))

                # Tentar encontrar imagem correspondente
                for img_path in page_images:
                    if img_path not in used_images:
                        # Inserir imagem logo após o parágrafo que a referencia
                        img_basename = os.path.basename(img_path)
                        caption = f"{ref_type.capitalize()} {ref_num}"
                        result.append("")
                        result.append(f"![{caption}]({img_path})")
                        result.append(f"*{caption}*")
                        result.append("")
                        used_images.add(img_path)
                        break

    return result


def find_duplicate_images(output_dir: str, min_occurrences: int = 2) -> List[str]:
    """
    Encontra imagens duplicadas (rodapés/cabeçalhos repetidos).

    Args:
        output_dir: Diretório com as imagens
        min_occurrences: Número mínimo de ocorrências para considerar duplicata

    Returns:
        Lista de caminhos de imagens duplicadas a serem removidas
    """
    img_dir = os.path.join(output_dir, "images")
    if not os.path.exists(img_dir):
        return []

    # Calcular hash de todas as imagens
    hash_to_files = {}

    for img_file in os.listdir(img_dir):
        img_path = os.path.join(img_dir, img_file)
        if not os.path.isfile(img_path):
            continue

        img_hash = calculate_image_hash(img_path)
        if not img_hash:
            continue

        if img_hash not in hash_to_files:
            hash_to_files[img_hash] = []
        hash_to_files[img_hash].append(img_file)

    # Identificar duplicatas (aparecem em várias páginas)
    duplicates = []

    for img_hash, files in hash_to_files.items():
        if len(files) >= min_occurrences:
            # Remover TODAS as ocorrências da duplicata (não manter nenhuma)
            logger.info(f"Found duplicate image appearing {len(files)} times - removing ALL")
            duplicates.extend(files)

    return duplicates


def process_pdf(pdf_path: str, output_dir: str) -> Tuple[str, str]:
    """
    Processa um PDF completo: extrai texto e todas as imagens.
    Remove apenas duplicatas (rodapés/cabeçalhos repetidos).

    Características:
    - Extrai TODAS as imagens primeiro
    - Remove apenas imagens duplicadas (que aparecem em múltiplas páginas)
    - Vincula imagens com referências explícitas no texto
    - Gera Markdown bem estruturado
    - Cria arquivo ZIP com tudo

    Args:
        pdf_path: Caminho do arquivo PDF
        output_dir: Diretório onde salvar Markdown e imagens

    Returns:
        Tupla (nome_arquivo_md, pasta_imagens)
    """
    logger.info(f"Starting PDF processing: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ValueError(f"Erro ao abrir PDF: {e}")

    os.makedirs(output_dir, exist_ok=True)
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    # Obter nome do PDF sem extensão
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]

    # Inicializar componentes
    image_mapper = ImageReferenceMapper()

    md_lines = []
    page_images = {}  # page_num -> lista de imagens
    total_images_extracted = 0
    referenced_images = []  # Imagens que foram referenciadas

    print("\n📄 Processando PDF...")
    print(f"   Total de páginas: {len(doc)}")

    # PRIMEIRA PASSAGEM: extrair TODAS as imagens
    print("\n🖼️  Extraindo todas as imagens...")
    for page_num, page in enumerate(doc, start=1):
        # Extrair TODAS as imagens (sem filtro)
        images = extract_images_from_page(doc, page, page_num, output_dir, pdf_name)

        if images:
            page_images[page_num] = images
            total_images_extracted += len(images)
            for img_path in images:
                image_mapper.add_image(page_num, img_path)
            print(f"   Página {page_num}: {len(images)} imagens extraídas")

    print(f"\n✓ Total de imagens extraídas: {total_images_extracted}")

    # SEGUNDA PASSAGEM: processar texto por página
    print("\n📝 Processando texto...")
    for page_num, page in enumerate(doc, start=1):
        # Extrair blocos de texto estruturados
        blocks = extract_text_blocks_from_page(page, page_num)

        # Consolidar em parágrafos
        paragraphs = consolidate_text_blocks(blocks)

        # Injetar imagens nos parágrafos baseado em referências
        page_content = _inject_images_in_paragraphs(
            paragraphs,
            page_images.get(page_num, []),
            page_num,
            image_mapper
        )

        # Rastrear imagens referenciadas
        for line in page_content:
            if "![" in line and "](" in line:
                # Extrair caminho da imagem
                match = re.search(r'\]\(([^)]+)\)', line)
                if match:
                    referenced_images.append(match.group(1))

        # Adicionar ao markdown
        md_lines.extend(page_content)

        # Quebra de página
        if page_num < len(doc):
            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

    doc.close()

    # Juntar linhas
    markdown_content = "\n".join(md_lines)

    # Limpar múltiplas quebras de linha
    markdown_content = re.sub(r"\n\n\n+", "\n\n", markdown_content)
    markdown_content = re.sub(r"[ \t]+\n", "\n", markdown_content)

    # Salvar Markdown
    md_filename = f"{pdf_name}.md"
    md_path = os.path.join(output_dir, md_filename)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content.strip())

    # Detectar e remover imagens duplicadas (rodapés/cabeçalhos)
    print("\n🧹 Detectando imagens duplicadas (rodapés/cabeçalhos)...")
    duplicates = find_duplicate_images(output_dir, min_occurrences=2)

    removed_duplicates = 0
    if duplicates:
        print(f"   Encontradas {len(duplicates)} imagens duplicadas")
        for img_file in duplicates:
            img_full_path = os.path.join(img_dir, img_file)
            img_rel_path = f"images/{img_file}"

            # Remover TODAS as duplicatas (rodapés/cabeçalhos sempre devem sair)
            try:
                if os.path.exists(img_full_path):
                    os.remove(img_full_path)
                    removed_duplicates += 1
                    logger.debug(f"Removed duplicate: {img_file}")

                    # Remover do rastreamento de referências também
                    if img_rel_path in referenced_images:
                        referenced_images.remove(img_rel_path)
            except Exception as e:
                logger.warning(f"Could not remove {img_file}: {e}")

    # Contar imagens finais
    final_image_count = len(os.listdir(img_dir)) if os.path.exists(img_dir) else 0

    print(f"\n   ✓ {removed_duplicates} imagens duplicadas removidas")
    print(f"   ✓ {final_image_count} imagens mantidas")
    print(f"   ✓ {len(referenced_images)} imagens referenciadas no texto")

    stats = {
        "total_images_extracted": total_images_extracted,
        "referenced_images": len(referenced_images),
        "duplicates_removed": removed_duplicates,
        "final_images": final_image_count,
        "output_markdown": md_path,
        "output_images_dir": img_dir,
    }

    print(f"\n✅ Processamento concluído!")
    print(f"   📊 Imagens extraídas: {stats['total_images_extracted']}")
    print(f"   📊 Duplicadas removidas: {stats['duplicates_removed']}")
    print(f"   📊 Imagens finais: {stats['final_images']}")
    print(f"   📊 Referenciadas no texto: {stats['referenced_images']}")
    print(f"   📄 Markdown salvo em: {md_path}")
    print(f"   📁 Imagens em: {img_dir}")

    # Criar arquivo ZIP com todo o conteúdo
    print(f"\n📦 Criando arquivo comprimido...")
    zip_filename = f"{pdf_name}_completo.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Adicionar Markdown
            if os.path.exists(md_path):
                zipf.write(md_path, arcname=md_filename)
                print(f"   ✓ Adicionado: {md_filename}")

            # Adicionar imagens
            if os.path.exists(img_dir):
                img_files = os.listdir(img_dir)
                for img_file in img_files:
                    img_full_path = os.path.join(img_dir, img_file)
                    if os.path.isfile(img_full_path):
                        arcname = os.path.join("images", img_file)
                        zipf.write(img_full_path, arcname=arcname)

                print(f"   ✓ Adicionado: pasta 'images' com {len(img_files)} imagens")

        zip_size = os.path.getsize(zip_path) / 1024
        print(f"   ✓ Tamanho do ZIP: {zip_size:.1f} KB")
        print(f"\n✅ Arquivo comprimido criado!")
        print(f"   📦 {zip_filename}")

    except Exception as e:
        logger.error(f"Erro ao criar ZIP: {e}")
        print(f"   ⚠️  Erro ao criar ZIP: {e}")

    return md_filename, "images"


def create_zip_export(output_dir: str, pdf_name: str) -> str:
    """
    Cria um arquivo ZIP com o Markdown e todas as imagens.

    Args:
        output_dir: Diretório com os arquivos
        pdf_name: Nome base do PDF

    Returns:
        Caminho do arquivo ZIP criado
    """
    zip_filename = f"{pdf_name}_completo.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    md_filename = f"{pdf_name}.md"
    md_path = os.path.join(output_dir, md_filename)
    img_dir = os.path.join(output_dir, "images")

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Adicionar Markdown
            if os.path.exists(md_path):
                zipf.write(md_path, arcname=md_filename)

            # Adicionar imagens
            if os.path.exists(img_dir):
                for img_file in os.listdir(img_dir):
                    img_full_path = os.path.join(img_dir, img_file)
                    if os.path.isfile(img_full_path):
                        arcname = os.path.join("images", img_file)
                        zipf.write(img_full_path, arcname=arcname)

        logger.info(f"ZIP created: {zip_path}")
        return zip_path

    except Exception as e:
        logger.error(f"Error creating ZIP: {e}")
        raise


def process_multiple_pdfs(pdf_paths: List[str], output_dir: str) -> str:
    """
    Processa múltiplos PDFs com todas as imagens consolidadas em uma única pasta.
    Gera Markdowns separados para cada PDF e um ZIP único com tudo.

    Características:
    - Processa múltiplos PDFs sequencialmente
    - Todas as imagens são salvas em uma única pasta "images/"
    - Detecta duplicatas globalmente (entre todos os PDFs)
    - Gera um arquivo Markdown por PDF
    - Cria um ZIP consolidado com todos os Markdowns e imagens

    Args:
        pdf_paths: Lista de caminhos para os PDFs
        output_dir: Diretório onde salvar tudo

    Returns:
        Nome do arquivo ZIP consolidado
    """
    logger.info(f"Starting multiple PDF processing: {len(pdf_paths)} files")

    if not pdf_paths or len(pdf_paths) == 0:
        raise ValueError("Nenhum arquivo PDF fornecido.")

    os.makedirs(output_dir, exist_ok=True)
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    # Inicializar componentes
    image_mapper = ImageReferenceMapper()
    md_files = []  # Lista de (nome_pdf, caminho_md)
    total_images_extracted = 0
    all_page_images = {}  # {pdf_index: {page_num: [images]}}
    referenced_images = []

    print("\n📚 Processando múltiplos PDFs...")
    print(f"   Total de arquivos: {len(pdf_paths)}")

    # PRIMEIRA PASSAGEM: extrair TODAS as imagens de TODOS os PDFs
    print("\n🖼️  Extraindo imagens de todos os PDFs...")
    for pdf_index, pdf_path in enumerate(pdf_paths):
        if not os.path.exists(pdf_path):
            raise ValueError(f"Arquivo PDF não encontrado: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise ValueError(f"Erro ao abrir PDF {pdf_path}: {e}")

        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        page_images = {}

        print(f"\n   📄 {pdf_name}.pdf ({len(doc)} páginas)")

        # Extrair imagens de todas as páginas deste PDF
        for page_num, page in enumerate(doc, start=1):
            images = extract_images_from_page(doc, page, page_num, output_dir, pdf_name)
            if images:
                page_images[page_num] = images
                total_images_extracted += len(images)
                for img_path in images:
                    image_mapper.add_image(page_num, img_path)
                print(f"      Página {page_num}: {len(images)} imagens extraídas")

        all_page_images[pdf_index] = page_images
        doc.close()

    print(f"\n✓ Total de imagens extraídas: {total_images_extracted}")

    # SEGUNDA PASSAGEM: processar texto de TODOS os PDFs
    print("\n📝 Processando texto de todos os PDFs...")
    for pdf_index, pdf_path in enumerate(pdf_paths):
        doc = fitz.open(pdf_path)
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        page_images = all_page_images.get(pdf_index, {})

        md_lines = []

        # Adicionar título do PDF
        md_lines.append(f"# {pdf_name}")
        md_lines.append("")

        for page_num, page in enumerate(doc, start=1):
            # Extrair blocos de texto estruturados
            blocks = extract_text_blocks_from_page(page, page_num)

            # Consolidar em parágrafos
            paragraphs = consolidate_text_blocks(blocks)

            # Injetar imagens nos parágrafos
            page_content = _inject_images_in_paragraphs(
                paragraphs,
                page_images.get(page_num, []),
                page_num,
                image_mapper
            )

            # Rastrear imagens referenciadas
            for line in page_content:
                if "![" in line and "](" in line:
                    match = re.search(r'\]\(([^)]+)\)', line)
                    if match:
                        referenced_images.append(match.group(1))

            # Adicionar ao markdown
            md_lines.extend(page_content)

            # Quebra de página
            if page_num < len(doc):
                md_lines.append("")
                md_lines.append("---")
                md_lines.append("")

        doc.close()

        # Juntar linhas e limpar
        markdown_content = "\n".join(md_lines)
        markdown_content = re.sub(r"\n\n\n+", "\n\n", markdown_content)
        markdown_content = re.sub(r"[ \t]+\n", "\n", markdown_content)

        # Salvar Markdown individual
        md_filename = f"{pdf_name}.md"
        md_path = os.path.join(output_dir, md_filename)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content.strip())

        md_files.append((pdf_name, md_filename, md_path))
        print(f"   ✓ {md_filename} criado")

    # Detectar e remover imagens duplicadas (rodapés/cabeçalhos)
    print("\n🧹 Detectando imagens duplicadas em todos os PDFs...")
    duplicates = find_duplicate_images(output_dir, min_occurrences=2)

    removed_duplicates = 0
    if duplicates:
        print(f"   Encontradas {len(duplicates)} imagens duplicadas")
        for img_file in duplicates:
            img_full_path = os.path.join(img_dir, img_file)
            img_rel_path = f"images/{img_file}"

            try:
                if os.path.exists(img_full_path):
                    os.remove(img_full_path)
                    removed_duplicates += 1
                    logger.debug(f"Removed duplicate: {img_file}")

                    if img_rel_path in referenced_images:
                        referenced_images.remove(img_rel_path)
            except Exception as e:
                logger.warning(f"Could not remove {img_file}: {e}")

    # Contar imagens finais
    final_image_count = len(os.listdir(img_dir)) if os.path.exists(img_dir) else 0

    print(f"\n   ✓ {removed_duplicates} imagens duplicadas removidas")
    print(f"   ✓ {final_image_count} imagens mantidas")
    print(f"   ✓ {len(referenced_images)} imagens referenciadas no texto")

    # Criar arquivo ZIP consolidado
    print(f"\n📦 Criando arquivo comprimido consolidado...")
    zip_filename = "consolidado_completo.zip"
    zip_path = os.path.join(output_dir, zip_filename)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Adicionar todos os Markdowns
            for pdf_name, md_filename, md_path in md_files:
                if os.path.exists(md_path):
                    zipf.write(md_path, arcname=md_filename)
                    print(f"   ✓ Adicionado: {md_filename}")

            # Adicionar imagens
            if os.path.exists(img_dir):
                img_files = os.listdir(img_dir)
                for img_file in img_files:
                    img_full_path = os.path.join(img_dir, img_file)
                    if os.path.isfile(img_full_path):
                        arcname = os.path.join("images", img_file)
                        zipf.write(img_full_path, arcname=arcname)

                print(f"   ✓ Adicionado: pasta 'images' com {len(img_files)} imagens")

        zip_size = os.path.getsize(zip_path) / 1024
        print(f"   ✓ Tamanho do ZIP: {zip_size:.1f} KB")
        print(f"\n✅ Processamento de múltiplos PDFs concluído!")
        print(f"   📦 {zip_filename}")

    except Exception as e:
        logger.error(f"Erro ao criar ZIP consolidado: {e}")
        print(f"   ⚠️  Erro ao criar ZIP: {e}")
        raise

    return zip_filename
