import os
import re
import zipfile
from typing import List, Tuple, Dict
import fitz
from app.utils.image_filter import ImageFilter
from app.utils.image_reference_mapper import ImageReferenceMapper
from app.utils.formula_detector import FormulaDetector, FormulaDetectorConfig, is_math_expression
from app.utils.text_cleaner import PDFTextCleaner, TextType
from app.utils.list_detector import ListDetector, get_list_detector
import logging
import hashlib
import io
from collections import Counter

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
    Extrai imagens de uma página do PDF aplicando filtros inteligentes.

    Args:
        doc: Documento PyMuPDF
        page: Página atual
        page_num: Número da página
        output_dir: Diretório para salvar imagens
        pdf_name: Nome do arquivo PDF (para prefixo)

    Returns:
        Lista de caminhos relativos das imagens extraídas (filtradas)
    """
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    image_paths = []
    image_count = 0
    filtered_count = 0

    # Inicializar filtro de imagens
    image_filter = ImageFilter()

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

                # Obter dados da imagem para filtros
                img_data = pix.tobytes()

                # Filtro: Remover cores sólidas (fundos, decorações)
                if image_filter.is_solid_color_image(img_data):
                    filtered_count += 1
                    logger.debug(f"Page {page_num}: Skipped solid color image {img_index}")
                    continue

                image_count += 1

                # Detectar formato
                ext = "png"
                try:
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

    if filtered_count > 0:
        logger.debug(f"Page {page_num}: Filtered {filtered_count} solid color images")

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
        text_dict = page.get_text("dict")  # type: ignore

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


def _is_header_or_footer(text: str, page_num: int, total_pages: int) -> bool:
    """
    Detecta se um texto é header ou footer repetido.
    Headers/footers são elementos de paginação que não fazem sentido em Markdown.

    Args:
        text: Texto a verificar
        page_num: Número da página atual
        total_pages: Total de páginas do documento

    Returns:
        True se for header/footer (deve ser removido)
    """
    text_clean = text.strip()

    if not text_clean or len(text_clean) < 2:
        return False

    # 1. Número de página puro (isolado)
    if re.match(r'^\d{1,4}$', text_clean):
        return True

    # 2. "Página X", "Página X de Y", "Page X", "Pág. X"
    if re.match(r'^(página|page|pág\.?)\s*\d+', text_clean, re.IGNORECASE):
        return True

    # 3. Código técnico de documento no início (ex: "HSN002 – Título...")
    # Padrões como: ABC123, AB-123, AB.123
    if re.match(r'^[A-Z]{2,}\d{2,}', text_clean):
        return True

    # 4. Texto com múltiplos espaços grandes (layout de header/footer)
    # Característico de: "Título    Autor    Instituição    Página"
    if text_clean.count('  ') >= 2 and len(text_clean) > 50:
        return True

    # 5. Linha que termina com número de página após espaços
    if re.search(r'\s{2,}\d{1,3}\s*$', text_clean):
        return True

    # 6. Padrões comuns de rodapé/cabeçalho institucional
    institutional_patterns = [
        r'universidade\s+(federal|estadual|de)',
        r'faculdade\s+de',
        r'instituto\s+(federal|de)',
        r'prof[aª]?\.\s',
        r'©\s*\d{4}',
        r'all\s+rights\s+reserved',
        r'todos\s+os\s+direitos',
    ]
    for pattern in institutional_patterns:
        if re.search(pattern, text_clean, re.IGNORECASE):
            # Só é header/footer se for linha curta ou tiver formato de cabeçalho
            if len(text_clean) < 150 or text_clean.count('  ') >= 1:
                return True

    # 7. Texto muito longo em uma única linha (provavelmente header espalhado)
    if len(text_clean) > 120 and '\n' not in text_clean:
        # Verificar se tem padrões de header
        if re.search(r'(–|—|-)\s*\d+\s*$', text_clean):
            return True

    return False


def _filter_repeated_headers_footers(blocks: List[Dict]) -> List[Dict]:
    """
    Filtra blocos de texto que são headers ou footers repetidos.
    Remove elementos de paginação que não fazem sentido em Markdown.

    Args:
        blocks: Lista de blocos de texto

    Returns:
        Lista de blocos sem headers/footers repetidos
    """
    if not blocks:
        return []

    total_pages = max(1, len(set(b["page"] for b in blocks)))

    # Identificar padrões repetidos (aparecem em múltiplas páginas)
    text_by_page: Dict[str, set] = {}
    for block_index, block in enumerate(blocks):
        # Normalizar texto para comparação (remover números no final, que podem ser página)
        text_norm = re.sub(r'\s+\d{1,3}\s*$', '', block["text"].strip().lower())
        text_norm = re.sub(r'\s+', ' ', text_norm)  # Normalizar espaços
        if text_norm not in text_by_page:
            text_by_page[text_norm] = set()
        text_by_page[text_norm].add(block.get("page", 0))

    # Textos que aparecem em muitas páginas são provavelmente headers/footers
    repeated_threshold = max(3, total_pages * 0.3)
    repeated_texts = {t for t, pages in text_by_page.items() if len(pages) >= repeated_threshold}

    # Filtrar blocos
    filtered = []
    for block_index, block in enumerate(blocks):
        text = block["text"].strip()
        page_num = block.get("page", 0)

        # Verificar se é header/footer por padrão
        if _is_header_or_footer(text, page_num, total_pages):
            continue

        # Verificar se é texto repetido em muitas páginas
        text_norm = re.sub(r'\s+\d{1,3}\s*$', '', text.lower())
        text_norm = re.sub(r'\s+', ' ', text_norm)
        if text_norm in repeated_texts:
            continue

        filtered.append(block)

    return filtered


# Instâncias globais
_text_cleaner = PDFTextCleaner()
_list_detector = get_list_detector()


def _is_garbage_text(text: str) -> bool:
    """
    Detecta se o texto é "lixo" que deve ser completamente removido.

    Inclui:
    - Sequências de símbolos sem sentido
    - Texto muito fragmentado
    - Linhas com apenas números e símbolos

    Args:
        text: Texto a verificar

    Returns:
        True se deve ser removido
    """
    if not text or len(text) < 3:
        return True

    text_clean = text.strip()

    # Apenas números, pontuação e espaços
    if re.match(r'^[\d\s\.\,\-–—:;/\\()]+$', text_clean):
        return True

    # Apenas símbolos matemáticos/gregos
    if re.match(r'^[\s$αβγδεζηθικλμνξπρστυφχψωρΓΔ∞∑∏∫∂∇√±×÷≤≥≠≈∈∉⊂⊃∪∩+\-*/^_=<>]+$', text_clean):
        return True

    # Muito poucas palavras legíveis em relação ao tamanho
    words = re.findall(r'\b[A-Za-zÀ-ú]{3,}\b', text_clean)
    if len(text_clean) > 20 and len(words) < 2:
        return True

    # Padrão de tabela de unidades fragmentada
    if re.search(r'(Sistema|MKS|CGS|S\.I\.)\s*[:\.]?\s*\w{1,3}\s+\w{1,3}', text_clean):
        return True

    return False


def _clean_pdf_artifacts(text: str) -> str:
    """
    Remove artefatos de PDF que não fazem sentido em Markdown.

    Inclui:
    - Números de página incorporados ao texto
    - Marcadores de página como "$14 Si$"
    - Headers/footers parciais que passaram pelo filtro
    - Caracteres de controle e espaços excessivos

    Args:
        text: Texto a limpar

    Returns:
        Texto limpo ou string vazia se o texto era apenas artefato
    """
    if not text:
        return ""

    # Usar o limpador de texto
    text = _text_cleaner.clean_text(text)

    if not text:
        return ""

    original_text = text

    # Remover headers técnicos parciais que possam ter passado
    # Ex: "HSN002 – Mecânica dos Fluidos"
    text = re.sub(r'^[A-Z]{2,}\d{2,}\s*[-–—]\s*[^.]+\s*$', '', text)

    # Limpar referências institucionais isoladas
    institutional = [
        r'^.*Universidade\s+Federal.*$',
        r'^.*Faculdade\s+de\s+Engenharia.*$',
        r'^Prof[aª]?\.\s+\w+.*$',
    ]
    for pattern in institutional:
        if re.match(pattern, text, re.IGNORECASE):
            # Só remover se for linha curta (provavelmente header/footer)
            if len(text) < 100:
                text = ''
                break

    # Remover linhas que ficaram apenas com pontuação ou números
    text = text.strip()
    if re.match(r'^[\d\s\.\,\-–—]+$', text):
        return ""

    # Se o texto ficou muito curto após limpeza e era maior antes,
    # provavelmente era artefato
    if len(text) < 3 and len(original_text) > 10:
        return ""

    return text.strip()


def _is_fragmented_formula(text: str) -> bool:
    """
    Detecta se o texto parece ser uma fórmula fragmentada/ilegível.

    Usa heurísticas simples baseadas em padrões.

    Args:
        text: Texto a verificar

    Returns:
        True se parece ser fórmula fragmentada
    """
    if not text or len(text) < 5:
        return False

    # Verificar se está muito fragmentado (muitas letras isoladas)
    isolated_letters = len(re.findall(r'\b[A-Za-z]\b', text))
    total_words = len(text.split())

    # Se mais de 50% são letras isoladas, está fragmentado
    if total_words > 3 and isolated_letters / total_words > 0.5:
        return True

    # Padrão de sequência fragmentada (muitas palavras curtas seguidas)
    if re.search(r'(\b\w{1,3}\b\s+){5,}', text):
        return True

    # Padrão de unidades fragmentadas
    if re.search(r'\b\w{1,3}\s+\w{1,3}\s*:\s*\w', text):
        return True

    # Muitos símbolos $ (LaTeX fragmentado)
    if text.count('$') >= 4:
        return True

    return False


def _clean_fragmented_formula(text: str) -> str:
    """
    Tenta limpar ou simplificar uma fórmula fragmentada.

    Usa heurísticas simples para extrair partes legíveis.

    Args:
        text: Texto da fórmula fragmentada

    Returns:
        Texto limpo ou string vazia se muito fragmentado
    """
    # Extrair número de equação se presente
    eq_match = re.search(r'\(?\s*(\d+[.,]\d+)\s*\)?', text)
    eq_label = eq_match.group(1) if eq_match else None

    # Tentar extrair palavras legíveis (mais de 3 caracteres)
    words = text.split()
    readable_words = [w for w in words if len(w) > 3 and w.isalpha()]
    readable_text = ' '.join(readable_words)

    # Se conseguiu extrair texto legível significativo
    if readable_text and len(readable_text) >= 10:
        if eq_label:
            return f'{readable_text} *(Eq. {eq_label})*'
        return readable_text

    # Se só tem número de equação
    if eq_label:
        return f'*(Equação {eq_label})*'

    # Fórmula muito fragmentada - retornar texto original (não remover)
    # O usuário pediu para não tentar reconstruir o que não funciona
    return text


def _should_use_llm_for_formulas(text: str) -> bool:
    """
    Decide se deve usar LLM para corrigir fórmulas no texto.
    
    Usa LLM para TODAS as fórmulas matemáticas para garantir conversão
    completa para LaTeX de alta qualidade.
    
    Args:
        text: Texto a verificar
        
    Returns:
        True se deve usar LLM, False para usar apenas detector local
    """
    if not text or len(text) > 500:
        # Textos muito longos provavelmente são parágrafos, não fórmulas
        return False
    
    # Detectar QUALQUER fórmula matemática
    formula_patterns = [
        # Letras gregas (indicadores fortes de fórmula)
        r'[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]',
        
        # Caracteres Unicode privados (usados por PDFs com fontes customizadas para símbolos matemáticos)
        # Range U+F000-U+F0FF é comum para símbolos em PDFs
        r'[\uf000-\uf0ff]',
        
        # Símbolos matemáticos
        r'[∞∑∏∫∂∇√±×÷≤≥≠≈∈∉⊂⊃∪∩∧∨¬→←↔⇒⇐⇔∀∃∄]',
        
        # Subscritos e superscritos Unicode
        r'[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₔₕₖₗₘₙₚₛₜ⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ]',
        
        # Operadores matemáticos com contexto
        r'[a-zA-Z]\s*[=＋\-\*/^]\s*[a-zA-Z0-9]',
        
        # Frações tipo a/b
        r'\w+\s*/\s*\w+',
        
        # Funções matemáticas
        r'\b(sen|cos|tan|log|ln|exp|lim|max|min|sin|sqrt|raiz)\b',
        
        # Símbolos matemáticos Unicode (funções, variáveis)
        r'[ƒ𝑓𝑔𝑥𝑦𝑧𝑎𝑏𝑐𝑛𝑚𝑘𝐴𝐵𝐶]',
        
        # Parênteses com conteúdo matemático
        r'\([^)]{2,20}\)\s*[=＋]',
        
        # Números com unidades
        r'\d+\s*[a-zA-Z/²³]+\s*[=＋]',
    ]
    
    # Contar quantos padrões de fórmula aparecem
    formula_score = 0
    for pattern in formula_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            formula_score += 1
    
    # Se tem pelo menos 2 indicadores ou caracteres matemáticos específicos, é fórmula
    if formula_score >= 2:
        return True
    
    # Se tem letras gregas isoladas, é quase certamente fórmula
    if re.search(r'[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]', text):
        return True
    
    # Fórmulas fragmentadas (letras isoladas)
    words = text.split()
    isolated_letters = len([w for w in words if len(w) == 1 and w.isalpha()])
    if len(words) > 2 and isolated_letters >= 2:
        return True
    
    return False

def _detect_heading_level(text: str, font_size: float, is_bold: bool, all_font_sizes: List[float]) -> int:
    """
    Detecta o nível de heading baseado em padrões e tamanho de fonte.

    Args:
        text: Texto do heading
        font_size: Tamanho da fonte
        is_bold: Se está em negrito
        all_font_sizes: Lista de todos os tamanhos de fonte únicos do documento

    Returns:
        Nível do heading (1-6) ou 0 se não for heading
    """
    text_upper = text.strip().upper()
    text_clean = text.strip()

    # NÃO é heading se for muito curto ou parecer fragmento de fórmula
    if len(text_clean) < 3:
        return 0

    # Não tratar como heading se parecer ser fragmento de fórmula ou variável
    # Ex: "Patm", "gH", símbolos isolados
    if re.match(r'^[A-Za-z]{1,5}$', text_clean) and not text_clean.isupper():
        return 0

    # Não tratar como heading se for "A integral", "O volume", etc (início de frase)
    if re.match(r'^(A|O|As|Os|Um|Uma)\s+\w+$', text_clean):
        return 0

    # NÃO é heading se parecer ser legenda de figura
    if re.match(r'^(Figura|Figure|Fig\.?|Tabela|Table|Tab\.?)\s*\d', text_clean, re.IGNORECASE):
        return 0

    # NÃO é heading se terminar com preposição (heading incompleto)
    # EXCETO se for ALL CAPS (título de documento)
    if re.search(r'\s+(de|do|da|dos|das|em|no|na|nos|nas|a|o|e|ou|para|com)\s*$', text_clean, re.IGNORECASE):
        if not text_clean.isupper():
            return 0

    # NÃO é heading se o número de seção for muito alto (provavelmente é referência de figura)
    section_match = re.match(r'^(\d+)\.(\d+)\s*[-–—]', text_clean)
    if section_match:
        sub_num = int(section_match.group(2))
        if sub_num > 12:
            return 0

    # Padrões para H1 (títulos principais)
    # "CAPÍTULO X", "PARTE X", "CHAPTER X"
    if re.match(r'^(CAPÍTULO|CAPITULO|PARTE|CHAPTER|UNIT)\s+\d+', text_upper):
        return 1

    # Título principal todo em maiúsculas com fonte grande
    if text_clean.isupper() and len(text_clean) > 5 and font_size > 16:
        return 1

    # "CAPÍTULO X – Título" combina CAPÍTULO com título
    if re.match(r'^(CAPÍTULO|CAPITULO|CHAPTER)\s+\d+\s*[-–—]\s*\S', text_upper):
        return 1

    # Padrões para H2/H3 baseado em numeração
    # "X.X - Título" ou "X.X – Título" (seção de primeiro nível com subseção)
    # Mas NÃO se for apenas "1 – A diferença" (conclusão numerada simples)
    if re.match(r'^\d+\.\d+\s*[-–—]?\s*[A-ZÀ-Ú]', text_clean) and not re.match(r'^\d+\.\d+\.\d+', text_clean):
        return 2

    # "X.X.X - Título" (subsubseção)
    if re.match(r'^\d+\.\d+\.\d+\s*[-–—]?\s*[A-ZÀ-Ú]', text_clean) and not re.match(r'^\d+\.\d+\.\d+\.\d+', text_clean):
        return 3

    # "X.X.X.X - Título" (subsubsubseção)
    if re.match(r'^\d+\.\d+\.\d+\.\d+', text_clean):
        return 4

    # Baseado em tamanho de fonte quando não há padrão claro
    # Mas só se tiver um tamanho de fonte significativamente maior
    if font_size > 18 and text_clean.isupper():
        return 1
    elif font_size > 16 and len(text_clean) < 80:
        return 2

    return 0


def _is_heading_candidate(text: str, font_size: float, is_bold: bool) -> bool:
    """
    Verifica se um texto é candidato a heading.

    Args:
        text: Texto a verificar
        font_size: Tamanho da fonte
        is_bold: Se está em negrito

    Returns:
        True se for candidato a heading
    """
    text_clean = text.strip()

    # Texto muito longo não é heading
    if len(text_clean) > 150:
        return False

    # Texto muito curto não é heading
    if len(text_clean) < 3:
        return False

    # Não é heading se parecer ser fragmento de fórmula ou variável
    # Ex: "Patm", "gH", símbolos matemáticos isolados
    if re.match(r'^[A-Za-z]{1,5}$', text_clean) and not text_clean.isupper():
        return False

    # Não é heading se for início de frase comum
    if re.match(r'^(A|O|As|Os|Um|Uma)\s+\w+$', text_clean):
        return False

    # Não é heading se for apenas número + texto curto sem estrutura de seção
    # Ex: "1 – A diferença" (conclusão numerada, não seção)
    if re.match(r'^[1-9]\s*[-–—]\s*[A-ZÀ-Ú]', text_clean) and '.' not in text_clean[:5]:
        # Verificar se não é uma seção real (seções têm formato X.X)
        return False

    # NÃO é heading se parecer ser legenda de figura
    # Ex: "2.15 – Componente vertical do esforço", "Figura 1.3: Esquema"
    if re.match(r'^(Figura|Figure|Fig\.?|Tabela|Table|Tab\.?)\s*\d', text_clean, re.IGNORECASE):
        return False

    # NÃO é heading se o número de seção for muito alto (provavelmente é referência)
    # Ex: "2.15 – ..." onde 15 é muito alto para uma subseção típica
    section_match = re.match(r'^(\d+)\.(\d+)\s*[-–—]', text_clean)
    if section_match:
        sub_num = int(section_match.group(2))
        if sub_num > 12:  # Subseções típicas vão até ~10
            return False

    # NÃO é heading se terminar com preposição ou artigo (heading incompleto)
    # EXCETO se for ALL CAPS (título de documento)
    if re.search(r'\s+(de|do|da|dos|das|em|no|na|nos|nas|a|o|e|ou|para|com)\s*$', text_clean, re.IGNORECASE):
        if not text_clean.isupper():
            return False

    # Padrões de heading por regex - APENAS padrões estruturais
    heading_patterns = [
        r'^(CAPÍTULO|CAPITULO|PARTE|CHAPTER|UNIT|SEÇÃO|SECAO|SECTION)\s+\d+',  # Capítulo X
        r'^\d+\.\d+\s*[-–—]?\s*[A-ZÀ-Ú]',  # 1.1 - Título ou 1.1 Título
        r'^\d+\.\d+\.\d+',  # 1.1.1
    ]

    for pattern in heading_patterns:
        if re.match(pattern, text_clean, re.IGNORECASE):
            return True

    # Fonte grande com texto em maiúsculas é heading
    if font_size > 16 and text_clean.isupper() and len(text_clean) > 5:
        return True

    # Negrito NÃO qualifica automaticamente como heading
    # Apenas padrões estruturais acima
    return False


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

    # Filtrar headers/footers repetidos
    blocks = _filter_repeated_headers_footers(blocks)

    if not blocks:
        return []

    paragraphs = []
    current_paragraph = []
    current_list_items = []  # Acumula itens de lista
    in_list = False
    last_font_size = None
    last_is_bold = False

    # Coletar tamanhos de fonte únicos para análise
    all_font_sizes = sorted(set(b["font_size"] for b in blocks), reverse=True)

    # Inicializar detector de fórmulas (heurístico)
    formula_config = FormulaDetectorConfig(
        min_confidence=0.5,
        wrap_inline=True,
        wrap_block=True,
        detect_fractions=True,
        detect_subscripts=True,
        detect_superscripts=True,
        detect_greek=True,
        detect_special_functions=True,
    )
    formula_detector = FormulaDetector(formula_config)

    # Usar detector de listas
    list_detector = _list_detector

    def _finalize_paragraph(block_index: int = -1):
        """Finaliza o parágrafo atual e processa listas inline."""
        nonlocal current_paragraph
        if current_paragraph:
            paragraph_text = " ".join(current_paragraph)
            # Verificar se o parágrafo contém lista inline
            if list_detector.has_inline_list(paragraph_text):
                processed = list_detector.process_paragraph(paragraph_text)
                # process_paragraph retorna texto com \n para listas
                for line in processed.split('\n'):
                    if line.strip():
                        paragraphs.append(line)
                    elif paragraphs and paragraphs[-1] != "":
                        paragraphs.append("")
            else:
                # Processar fórmulas com detector local primeiro
                paragraph_text = formula_detector.process_text(paragraph_text)
                
                # Verificar se precisa de LLM para converter fórmulas
                needs_llm = _should_use_llm_for_formulas(paragraph_text)

                if needs_llm:
                    from app.utils.api_formula_converter import get_api_converter
                    api_converter = get_api_converter()
                    if api_converter.is_available():
                        try:
                            # Coletar contexto (texto dos blocos anterior e posterior)
                            context_before = ""
                            context_after = ""
                            if block_index > 0:
                                prev_blocks = blocks[max(0, block_index-3):block_index]
                                context_before = " ".join([b["text"].strip() for b in prev_blocks])
                            if block_index < len(blocks) - 1:
                                next_blocks = blocks[block_index+1:min(len(blocks), block_index+4)]
                                context_after = " ".join([b["text"].strip() for b in next_blocks])

                            # Usar batch processing com chunking automático
                            paragraph_text, api_calls = api_converter.fix_paragraphs_batch(
                                paragraph_text,
                                context_before=context_before,
                                context_after=context_after
                            )
                            if api_calls > 0:
                                print(f"      🤖 Processado: {api_calls} chamada(s) API", flush=True)
                        except Exception as e:
                            logger.warning(f"API batch falhou, usando detector local: {e}")
                            pass
                
                paragraphs.append(paragraph_text)
    def _finalize_list():
        """Finaliza a lista atual."""
        nonlocal current_list_items, in_list
        if current_list_items:
            for item in current_list_items:
                paragraphs.append(item)
            paragraphs.append("")  # Linha em branco após lista
            current_list_items = []
        in_list = False

    for block_index, block in enumerate(blocks):
        text = block["text"].strip()

        # Limpar artefatos de PDF (números de página, headers parciais, etc.)
        text = _clean_pdf_artifacts(text)

        # Pular se ficou vazio após limpeza
        if not text:
            continue

        # Verificar se é texto "lixo"
        if _is_garbage_text(text):
            continue

        # DESATIVADO: Não remover fórmulas fragmentadas. O LLM contextual tentará consertá-las.
        # if _is_fragmented_formula(text):
        #     text = _clean_fragmented_formula(text)
        #     if not text:
        #         continue

        font_size = block["font_size"]
        is_bold = bool(block["font_flags"] & 2**4)  # Flag de negrito

        # NOVA LÓGICA: Detectar itens de lista (antes de verificar headings)
        if list_detector.is_list_item(text):
            # Finalizar parágrafo anterior se houver
            if current_paragraph:
                _finalize_paragraph(block_index)

            # Formatar item de lista
            formatted_item = list_detector.format_list_item(text)

            # Processar fórmulas no item de lista também
            formatted_item = formula_detector.process_text(formatted_item)
            if _should_use_llm_for_formulas(formatted_item):
                from app.utils.api_formula_converter import get_api_converter
                api_converter = get_api_converter()
                if api_converter.is_available():
                    try:
                        # Usar batch processing para listas também
                        formatted_item, api_calls = api_converter.fix_paragraphs_batch(formatted_item)
                    except Exception as e:
                        logger.warning(f"API batch falhou para lista: {e}")
            
            current_list_items.append(formatted_item)
            in_list = True
            last_font_size = font_size
            last_is_bold = is_bold
            continue

        # Se estava em lista, verificar se é continuação do item anterior
        # (texto fragmentado que faz parte do último item)
        if in_list and current_list_items:
            # Heurística: é continuação se:
            # 1. Texto curto (< 50 chars)
            # 2. Começa com letra minúscula ou é apenas uma palavra
            # 3. Termina com ; ou , (continuação de lista)
            # 4. Não é heading ou outro elemento estrutural
            is_continuation = False
            text_stripped = text.strip()

            if len(text_stripped) < 60:
                # Começa com minúscula ou é palavra isolada
                if text_stripped[0].islower() or len(text_stripped.split()) <= 2:
                    is_continuation = True
                # Termina com ponto-e-vírgula (continuação de item)
                if text_stripped.endswith(';'):
                    is_continuation = True

            if is_continuation and not _is_heading_candidate(text, font_size, is_bold):
                # Anexar ao último item da lista
                last_item = current_list_items[-1]
                # Remover o "- " do início para reconstruir
                if last_item.startswith('- '):
                    current_list_items[-1] = f"- {last_item[2:]} {text_stripped}"
                else:
                    current_list_items[-1] = f"{last_item} {text_stripped}"
                last_font_size = font_size
                last_is_bold = is_bold
                continue

        # Se estava em lista mas este bloco não é item nem continuação, finalizar lista
        if in_list:
            _finalize_list()

        # Detectar se é candidato a heading
        is_heading = _is_heading_candidate(text, font_size, is_bold)

        # Se for heading, finalizar parágrafo anterior
        if is_heading:
            if current_paragraph:
                _finalize_paragraph(block_index)

            # Detectar nível do heading
            level = _detect_heading_level(text, font_size, is_bold, all_font_sizes)

            if level > 0:
                # Adicionar heading com nível correto
                prefix = "#" * level
                paragraphs.append(f"{prefix} {text}")
            else:
                # Fallback para negrito se não for heading estrutural
                paragraphs.append(f"**{text}**")

            last_font_size = font_size
            last_is_bold = is_bold
            continue

        # Se for apenas negrito (sem ser heading), adicionar como negrito no parágrafo
        if is_bold and len(text) < 100:
            # Adicionar negrito inline ao invés de criar heading
            if current_paragraph:
                # Se há parágrafo anterior, combinar
                current_paragraph.append(f"**{text}**")
            else:
                # Caso contrário, criar parágrafo com apenas negrito
                current_paragraph.append(f"**{text}**")
            last_font_size = font_size
            last_is_bold = is_bold
            continue

        # Verificar se a linha é uma fórmula em bloco usando detector heurístico
        if formula_detector.is_formula_line(text):
            # Finalizar parágrafo anterior
            if current_paragraph:
                _finalize_paragraph(block_index)

            # Processar e adicionar fórmula como bloco
            formatted = formula_detector.format_formula_block(text)
            paragraphs.append(formatted)
            continue

        # Detectar quebra de parágrafo
        should_break = False

        # Mudança significativa de fonte
        if last_font_size and abs(font_size - last_font_size) > 2:
            should_break = True

        # Linha termina com ponto e próxima começa com maiúscula
        if (current_paragraph and
            current_paragraph[-1].endswith(".") and
            text and text[0].isupper()):
            should_break = True

        # Lista ou item enumerado (padrão legado)
        if re.match(r'^[\d\-•]\s', text):
            should_break = True

        if should_break and current_paragraph:
            _finalize_paragraph(block_index)

        # Adicionar texto ao parágrafo atual
        current_paragraph.append(text)
        last_font_size = font_size
        last_is_bold = is_bold

    # Finalizar lista pendente
    if in_list:
        _finalize_list()

    # Adicionar último parágrafo
    if current_paragraph:
        _finalize_paragraph(block_index)

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

    # Se não há imagens, retorna parágrafos como estão
    if not page_images:
        return paragraphs

    # Adiciona imagens no final da página se houver
    result.extend(paragraphs)

    # Inserir imagens da página no final
    for img_path in page_images:
        img_basename = os.path.basename(img_path)
        # Extrair número da imagem do nome do arquivo (ex: aula1_pag2_img1.png -> 1)
        img_num_match = re.search(r'_img(\d+)', img_basename)
        img_num = img_num_match.group(1) if img_num_match else "1"

        result.append("")
        result.append(f"![Figura {img_num}]({img_path})")
        result.append(f"*Figura {img_num}*")
        result.append("")

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
    for page_num, page in enumerate(doc, start=1):  # type: ignore
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
    for page_num, page in enumerate(doc, start=1):  # type: ignore
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
        for page_num, page in enumerate(doc, start=1):  # type: ignore
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
    total_pages_all = sum(fitz.open(p).page_count for p in pdf_paths)
    print(f"   Total de páginas a processar: {total_pages_all}")
    
    for pdf_index, pdf_path in enumerate(pdf_paths):
        doc = fitz.open(pdf_path)
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        page_images = all_page_images.get(pdf_index, {})

        md_lines = []

        # Adicionar título do PDF
        md_lines.append(f"# {pdf_name}")
        md_lines.append("")

        print(f"\n   📄 {pdf_name}.pdf ({len(doc)} páginas):")
        
        for page_num, page in enumerate(doc, start=1):  # type: ignore
            print(f"      Página {page_num}/{len(doc)}...", end=" ", flush=True)
            
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
            
            print("✓")

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
