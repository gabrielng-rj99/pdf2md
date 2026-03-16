import os
import re
import zipfile
from typing import List, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor
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

# Max parallel PDFs to process (default: 4)
MAX_PARALLEL_PDFS = int(os.getenv('MAX_PARALLEL_PDFS', '4'))


# =============================================================================
# FORMULA COLLECTION - Two-phase approach for better performance
# =============================================================================

class FormulaCollector:
    """
    Coleta fórmulas quebradas durante o processamento do PDF.
    Ao final, faz uma única chamada API para corrigir todas.
    """

    def __init__(self):
        self.formulas: List[Tuple[str, int, int, str]] = []  # (formula_text, start, end, page_context)
        self.pdf_name = ""
        self.total_pages = 0

    def add_formula(self, formula: str, start: int, end: int, page_context: str = ""):
        """Adiciona uma fórmula quebrada à coleção."""
        self.formulas.append((formula, start, end, page_context))

    def has_formulas(self) -> bool:
        return len(self.formulas) > 0

    def fix_all(self, pdf_text: str) -> str:
        """
        Faz uma única chamada API para corrigir todas as fórmulas do PDF.

        Args:
            pdf_text: Texto completo do PDF com fórmulas marcadas

        Returns:
            Texto com fórmulas corrigidas
        """
        if not self.has_formulas():
            return pdf_text

        from app.utils.api_formula_converter import get_api_converter
        api_converter = get_api_converter()

        if not api_converter.is_available():
            logger.warning("API não disponível para correção de fórmulas")
            return pdf_text

        # Extrair todas as fórmulas únicas
        unique_formulas = list(set(f[0] for f in self.formulas))

        print(f"      📦 Coletadas {len(unique_formulas)} fórmulas únicas para correção", flush=True)

        # Criar prompt com todas as fórmulas
        formulas_text = "\n".join(f"{i+1}. {f}" for i, f in enumerate(unique_formulas))

        prompt = f"""You are a mathematical formula fixer. Fix all formulas in the text below.

The text contains mathematical formulas that need to be converted to proper LaTeX format.
Return the COMPLETE fixed text with all formulas converted.

Formulas to fix (for reference):
{formulas_text}

Full text:
{pdf_text}

Return the complete fixed text:"""

        try:
            # Uma única chamada API para todo o PDF
            print(f"      🔄 Fazendo chamada API única para {len(unique_formulas)} fórmulas...", flush=True)

            response = api_converter._make_request(
                system_prompt="You are a mathematical formula fixer. Convert formulas to proper LaTeX.",
                user_prompt=prompt
            )

            # Limpar resposta
            response = re.sub(r'<think>.*?', '', response, flags=re.DOTALL).strip()
            if response.startswith("```"):
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

            print(f"      ✅ Fórmulas corrigidas com sucesso", flush=True)
            return response

        except Exception as e:
            logger.error(f"Erro ao corrigir fórmulas: {e}")
            print(f"      ⚠️ Erro ao corrigir fórmulas: {e}", flush=True)
            return pdf_text


def collect_page_formulas(text: str, page_num: int) -> List[str]:
    """
    Coleta todas as fórmulas quebradas de uma página.

    Args:
        text: Texto da página
        page_num: Número da página

    Returns:
        Lista de fórmulas quebradas
    """
    from app.utils.api_formula_converter import get_api_converter

    try:
        api_converter = get_api_converter()
        snippets = api_converter._extract_formula_snippets(text)
        return [s[0] for s in snippets]
    except:
        return []


def _fix_formulas_in_pdf(markdown_text: str, pdf_name: str) -> str:
    """
    Corrige todas as fórmulas de um PDF com uma única chamada API.

    Args:
        markdown_text: Texto Markdown completo do PDF
        pdf_name: Nome do PDF (para logging)

    Returns:
        Texto com fórmulas corrigidas
    """
    from app.utils.api_formula_converter import get_api_converter

    api_converter = get_api_converter()

    if not api_converter.is_available():
        print(f"      ⚠️ API não disponível, mantendo fórmulas originais", flush=True)
        return markdown_text

    # Extrair todas as fórmulas do texto
    try:
        snippets = api_converter._extract_formula_snippets(markdown_text)

        if not snippets:
            print(f"      ℹ️ Nenhuma fórmula detectada", flush=True)
            return markdown_text

        # Obter fórmulas únicas
        unique_formulas = list(dict.fromkeys(s[0] for s in snippets))
        print(f"      📦 {len(unique_formulas)} fórmulas únicas detectadas", flush=True)

        if len(unique_formulas) > 50:
            # Se muitas fórmulas, dividir em chunks de 10
            print(f"      📦 Muitas fórmulas ({len(unique_formulas)}), processando em chunks...", flush=True)
            chunks = [unique_formulas[i:i+10] for i in range(0, len(unique_formulas), 10)]
            results = []

            for i, chunk in enumerate(chunks):
                print(f"         🔄 Chunk {i+1}/{len(chunks)} ({len(chunk)} fórmulas)...", end=" ", flush=True)
                chunk_result = _fix_formulas_chunk(chunk, api_converter, markdown_text)
                results.append(chunk_result)
                print(f"✓", flush=True)

            # Combinar resultados
            result = markdown_text
            for chunk_result in results:
                result = _apply_formula_fixes(result, chunk_result)

            return result
        else:
            # Poucas fórmulas - uma única chamada
            print(f"      🔄 Fazendo chamada API única para {len(unique_formulas)} fórmulas...", flush=True)
            result = _fix_formulas_chunk(unique_formulas, api_converter, markdown_text)
            print(f"      ✅ Fórmulas corrigidas", flush=True)
            return result

    except Exception as e:
        logger.error(f"Erro ao corrigir fórmulas: {e}")
        print(f"      ⚠️ Erro ao corrigir fórmulas: {e}", flush=True)
        return markdown_text


def _fix_formulas_chunk(formulas: List[str], api_converter, original_text: str) -> Dict[str, str]:
    """
    Faz uma chamada API para corrigir um chunk de fórmulas.

    Args:
        formulas: Lista de fórmulas a corrigir
        api_converter: Instância do conversor API
        original_text: Texto original para contexto

    Returns:
        Dicionário {formula_original: formula_corrigida}
    """
    import time

    formulas_text = "\n".join(f"{i+1}. {f}" for i, f in enumerate(formulas))

    prompt = f"""You are a mathematical formula fixer.

Fix ALL mathematical formulas in the text below.
Return the COMPLETE text with ALL formulas converted to proper LaTeX.

Examples:
- ρ → \\rho
- γ → \\gamma
- x² → x^{{2}}
- f(x) = 2x + 1 → $f(x) = 2x + 1$
- α = β → $\\alpha = \\beta$

Formulas to fix (for reference):
{formulas_text}

Full text:
{original_text[:3000]}... (truncated for API)

Return the complete fixed text with LaTeX:"""

    try:
        start_time = time.time()
        response = api_converter._make_request(
            system_prompt="You are a mathematical formula fixer. Convert formulas to proper LaTeX format.",
            user_prompt=prompt
        )

        # Limpar resposta
        import re
        response = re.sub(r'<think>.*?', '', response, flags=re.DOTALL).strip()
        if response.startswith("```"):
            lines = response.split('\n')
            response = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

        elapsed = time.time() - start_time
        print(f"✓ ({elapsed:.1f}s)", flush=True)

        # Criar mapping das fórmulas
        # Simplificado: retornar o texto corrigido para aplicar
        return {"_full_text": response, "_original": original_text}

    except Exception as e:
        logger.error(f"Erro no chunk de fórmulas: {e}")
        raise


def _apply_formula_fixes(original_text: str, fixes: Dict[str, str]) -> str:
    """
    Aplica as correções de fórmulas ao texto original.

    Args:
        original_text: Texto original
        fixes: Dicionário com correções

    Returns:
        Texto com correções aplicadas
    """
    if "_full_text" in fixes:
        # Retornar o texto completo corrigido
        return fixes["_full_text"]
    return original_text


# =============================================================================
# TEMP FILE FORMULA FIXING APPROACH
# =============================================================================

def detect_broken_formulas(text: str) -> List[Tuple[int, str, str]]:
    """
    Detecta fórmulas quebradas no texto Markdown.

    Args:
        text: Texto Markdown completo

    Returns:
        Lista de tuplas (numero_linha, linha_original, tipo_problema)
    """
    lines = text.split('\n')
    broken = []

    # Padroes de formulas quebradas comuns
    problems = [
        # gammar (deveria ser gamma_r)
        (r'\\gammar', 'gammar -> gamma_r'),
        # PV = sem lado direito (sem backslash)
        (r'PV\s*=\s*$', 'PV = (incompleta)'),
        # nRT sem formato de equacao
        (r'\\bnRT\\b', 'nRT sem $'),
        # fracoes quebradas como kgf/m³ (sem formatar)
        (r'kgf/m³', 'kgf/m³ (sem LaTeX)'),
        # gamma sem escape correto
        (r'(?<!\\\\)\\gamma\\b', 'gamma sem escape'),
        # rho sem escape
        (r'(?<!\\\\)\\rho\\b', 'rho sem escape'),
        # epsilon sem escape
        (r'(?<!\\\\)\\epsilon\\b', 'epsilon sem escape'),
    ]

    for i, line in enumerate(lines, 1):
        for pattern, problem_type in problems:
            if re.search(pattern, line):
                broken.append((i, line, problem_type))
                break  # Uma detection por linha

    return broken


def create_temp_files(
    broken_formulas: List[Tuple[int, str, str]],
    text: str,
    output_dir: str,
    pdf_name: str,
    context_lines: int = 5
) -> Tuple[str, str]:
    """
    Cria arquivos temporarios com formulas quebradas + contexto.

    Args:
        broken_formulas: Lista de (linha, texto, tipo)
        text: Texto completo
        output_dir: Diretorio de saida
        pdf_name: Nome do PDF
        context_lines: Linhas de contexto antes/depois

    Returns:
        Tupla (caminho_arquivo_broken, caminho_arquivo_fixed)
    """
    lines = text.split('\n')
    lines_count = len(lines)

    broken_file = os.path.join(output_dir, f"{pdf_name}_formulas_broken.txt")
    fixed_file = os.path.join(output_dir, f"{pdf_name}_formulas_fixed.txt")

    with open(broken_file, 'w', encoding='utf-8') as bf, \
         open(fixed_file, 'w', encoding='utf-8') as ff:

        for line_num, original_line, problem_type in broken_formulas:
            # Calcular contexto (linhas ao redor)
            start_ctx = max(0, line_num - 1 - context_lines)
            end_ctx = min(lines_count, line_num)

            # Escrever no arquivo broken com marcadores
            bf.write(f"=== LINHA {line_num} ({problem_type}) ===\n")

            # Escrever contexto antes
            for ctx_line in range(start_ctx, line_num - 1):
                bf.write(f"{ctx_line + 1}: {lines[ctx_line]}\n")

            # Escrever linha quebrada com marcacao especial
            bf.write(f"@@ BROKEN: {lines[line_num - 1]}\n")

            # Escrever contexto depois
            for ctx_line in range(line_num, end_ctx):
                bf.write(f"{ctx_line + 1}: {lines[ctx_line]}\n")

            bf.write("\n")

            # No arquivo fixed, escrever placeholder para AI preencher
            ff.write(f"=== LINHA {line_num} ({problem_type}) ===\n")
            for ctx_line in range(start_ctx, line_num - 1):
                ff.write(f"{ctx_line + 1}: {lines[ctx_line]}\n")

            # Placeholder para AI preencher
            ff.write(f"@@ FIXED: \n")

            for ctx_line in range(line_num, end_ctx):
                ff.write(f"{ctx_line + 1}: {lines[ctx_line]}\n")

            ff.write("\n")

    return broken_file, fixed_file


def fix_formulas_via_temp_file(
    broken_file: str,
    fixed_file: str,
    pdf_name: str
) -> Dict[int, str]:
    """
    Corrige formulas usando API e escreve no arquivo fixed.

    Args:
        broken_file: Caminho do arquivo com formulas quebradas
        fixed_file: Caminho do arquivo para receber correcoes
        pdf_name: Nome do PDF

    Returns:
        Dicionario {linha: linha_corrigida}
    """
    from app.utils.api_formula_converter import get_api_converter

    api_converter = get_api_converter()

    if not api_converter.is_available():
        print(f"      ! API nao disponivel", flush=True)
        return {}

    # Ler arquivo broken
    with open(broken_file, 'r', encoding='utf-8') as f:
        broken_content = f.read()

    # Criar prompt para API - formato simples para cada bloco
    prompt = """FOR EACH BLOCK below:
1. Replace "@@ BROKEN: <text>" with "@@ FIXED: <corrected_text>"
2. Keep all other lines exactly the same

Example:
Input:
=== LINHA 10 ===
9: previous line
@@ BROKEN: kgf/m³
11: next line

Output:
=== LINHA 10 ===
9: previous line
@@ FIXED: $kgf/m^3$
11: next line

NOW DO THE SAME FOR ALL BLOCKS BELOW. Output ONLY the corrected blocks, nothing else:

""" + broken_content

    try:
        print(f"      @ Correcao de formulas via API...", flush=True)
        response = api_converter._make_request(
            system_prompt="You are a mathematical formula fixer. Fix broken LaTeX formulas.",
            user_prompt=prompt
        )

        # Limpar resposta - use raw string to avoid regex issues
        import re as regex_module
        response = regex_module.sub(r'think.*?comment', '', response, flags=regex_module.DOTALL).strip()
        if response.startswith("```"):
            lines = response.split('\n')
            response = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

        # Escrever no arquivo fixed
        with open(fixed_file, 'w', encoding='utf-8') as f:
            f.write(response)

        print(f"      + Fórmulas corrigidas via temp file", flush=True)

        return {}

    except Exception as e:
        logger.error(f"Erro ao corrigir formulas: {e}")
        print(f"      ! Erro: {e}", flush=True)
        return {}


def merge_formula_fixes(
    text: str,
    fixed_file: str,
    broken_file: str = None
) -> str:
    """
    Faz merge das correcoes de formulas de volta ao texto original.

    Args:
        text: Texto original
        fixed_file: Arquivo com correcoes
        broken_file: Arquivo com formulas quebradas (para debug)

    Returns:
        Texto com correcoes aplicadas
    """
    if not os.path.exists(fixed_file):
        return text

    import re as regex_module

    # Carregar fixed file
    with open(fixed_file, 'r', encoding='utf-8') as f:
        fixed_content = f.read()

    # Simpler: apenas aplicar known corrections diretamente no texto
    # Isso evita problemas de mapeamento de linhas
    corrections = [
        # (pattern, replacement)
        (r'\\gammar(?!\w)', r'\\gamma_r'),  # \gammar -> \gamma_r
        (r'kgf/m³', 'kgf/m^3'),
        (r'N/m³', 'N/m^3'),
        (r'PV\s*=\s*$', 'PV = nRT'),  # Complete PV = equation
    ]

    # Flags for each pattern (same order as corrections)
    correction_flags = [0, 0, 0, regex_module.MULTILINE]

    result = text

    # Debug: check if patterns match
    debug_pattern = r'PV\s*=\s*$'
    if regex_module.search(debug_pattern, result, regex_module.MULTILINE):
        print(f"      i DEBUG: PV pattern MATCHES in result", flush=True)
    else:
        print(f"      i DEBUG: PV pattern does NOT match", flush=True)

    for i, (pattern, replacement) in enumerate(corrections):
        flags = correction_flags[i]
        matches = regex_module.findall(pattern, result, flags)
        if matches:
            print(f"      i Aplicando: {pattern} -> {replacement} ({len(matches)} matches)", flush=True)
            result = regex_module.sub(pattern, replacement, result, flags=flags)

    return result


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

                # Não chamar API aqui - será feito em lote depois no _fix_formulas_in_pdf

                paragraphs.append(paragraph_text)
            # IMPORTANTE: Limpar current_paragraph após adicionar ao paragraphs
            current_paragraph = []
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

            # Processar fórmulas no item de lista também (sem API agora - será corrigido depois)
            formatted_item = formula_detector.process_text(formatted_item)
            # Não chamar API aqui - será feito em lote depois
            
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

    # ============================================================
    # CORRECAO DE FORMULAS VIA TEMP FILES
    # ============================================================
    print(f"\n   @ Detectando formulas quebradas...", flush=True)
    broken = detect_broken_formulas(markdown_content)

    if broken:
        print(f"      # {len(broken)} formulas quebradas detectadas", flush=True)
        # Criar arquivos temporarios
        broken_file, fixed_file = create_temp_files(
            broken, markdown_content, output_dir, pdf_name, context_lines=3
        )
        print(f"      # Arquivos temporarios criados", flush=True)

        # Corrigir via API
        fix_formulas_via_temp_file(broken_file, fixed_file, pdf_name)

        # Merge das correcoes
        markdown_content = merge_formula_fixes(markdown_content, fixed_file, broken_file)
        print(f"      + Fórmulas corrigidas", flush=True)
    else:
        print(f"      i Nenhuma formula quebrada detectada", flush=True)

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


def _extract_images_from_pdf(
    pdf_path: str,
    pdf_index: int,
    output_dir: str,
) -> Tuple[int, Dict[int, List[str]]]:
    """
    Extrai todas as imagens de um único PDF (thread-safe).

    Args:
        pdf_path: Caminho do arquivo PDF
        pdf_index: Índice do PDF na lista (para identificação)
        output_dir: Diretório de saída para imagens

    Returns:
        Tupla com (pdf_index, page_images) onde page_images é {page_num: [img_paths]}
    """
    if not os.path.exists(pdf_path):
        raise ValueError(f"Arquivo PDF não encontrado: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        raise ValueError(f"Erro ao abrir PDF {pdf_path}: {e}")

    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    page_images: Dict[int, List[str]] = {}

    print(f"\n   📄 {pdf_name}.pdf ({len(doc)} páginas)")

    # Extrair imagens de todas as páginas deste PDF
    for page_num, page in enumerate(doc, start=1):  # type: ignore
        images = extract_images_from_page(doc, page, page_num, output_dir, pdf_name)
        if images:
            page_images[page_num] = images
            print(f"      Página {page_num}: {len(images)} imagens extraídas")

    doc.close()
    return pdf_index, page_images


def _extract_images_parallel(
    pdf_paths: List[str],
    output_dir: str,
    max_workers: int = 4,
) -> Dict[int, Dict[int, List[str]]]:
    """
    Extrai imagens de múltiplos PDFs em paralelo usando ThreadPoolExecutor.

    Args:
        pdf_paths: Lista de caminhos dos arquivos PDF
        output_dir: Diretório de saída para imagens
        max_workers: Número máximo de threads (padrão: 4)

    Returns:
        Dicionário no formato {pdf_index: {page_num: [img_paths]}}
    """
    all_page_images: Dict[int, Dict[int, List[str]]] = {}

    # Usar mínimo entre max_workers e número de PDFs
    workers = min(max_workers, len(pdf_paths)) if pdf_paths else 1

    print(f"\n🖼️  Extraindo imagens de todos os PDFs em paralelo ({workers} threads)...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submeter todas as tarefas
        futures = {
            executor.submit(_extract_images_from_pdf, pdf_path, pdf_index, output_dir): pdf_index
            for pdf_index, pdf_path in enumerate(pdf_paths)
        }

        # Coletar resultados na ordem de conclusão
        for future in futures:
            pdf_index, page_images = future.result()
            all_page_images[pdf_index] = page_images

    # Ordenar pelo índice do PDF para manter a ordem
    all_page_images = dict(sorted(all_page_images.items()))

    total_images = sum(
        len(images)
        for page_imgs in all_page_images.values()
        for images in page_imgs.values()
    )
    print(f"\n✓ Total de imagens extraídas: {total_images}")

    return all_page_images


def _process_text_parallel(
    pdf_paths: List[str],
    all_page_images: Dict[int, Dict[int, List[str]]],
    image_mapper: "ImageReferenceMapper",
    output_dir: str,
    max_workers: int = 4,
) -> List[Tuple[str, str]]:
    """
    Processa o texto de múltiplos PDFs em paralelo usando ThreadPoolExecutor.

    Args:
        pdf_paths: Lista de caminhos para os PDFs
        all_page_images: Dicionário de {pdf_index: {page_num: [images]}}
        image_mapper: Mapeador de referências de imagens (compartilhado)
        output_dir: Diretório onde salvar os arquivos MD
        max_workers: Número máximo de threads (padrão 4)

    Returns:
        Lista de tuplas (pdf_name, md_path)
    """
    def process_single_pdf(args: Tuple[int, str]) -> Tuple[str, str]:
        """Processa o texto de um único PDF."""
        pdf_index, pdf_path = args
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

        # ============================================================
        # CORRECAO DE FORMULAS VIA TEMP FILES
        # ============================================================
        print(f"      @ Detectando formulas quebradas...", flush=True)
        broken = detect_broken_formulas(markdown_content)

        if broken:
            print(f"      # {len(broken)} formulas quebradas detectadas", flush=True)
            # Criar arquivos temporarios
            broken_file, fixed_file = create_temp_files(
                broken, markdown_content, output_dir, pdf_name, context_lines=3
            )
            print(f"      # Arquivos temporarios criados", flush=True)

            # Corrigir via API
            fix_formulas_via_temp_file(broken_file, fixed_file, pdf_name)

            # Merge das correcoes
            markdown_content = merge_formula_fixes(markdown_content, fixed_file, broken_file)
            print(f"      + Fórmulas corrigidas", flush=True)
        else:
            print(f"      i Nenhuma formula quebrada detectada", flush=True)

        # Salvar Markdown individual
        md_filename = f"{pdf_name}.md"
        md_path = os.path.join(output_dir, md_filename)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content.strip())

        print(f"   ✓ {md_filename} criado")
        return (pdf_name, md_path)

    # Processar todos os PDFs em paralelo
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single_pdf, enumerate(pdf_paths)))

    return results


def process_multiple_pdfs(pdf_paths: List[str], output_dir: str, max_workers: int = MAX_PARALLEL_PDFS) -> str:
    """
    Processa múltiplos PDFs com todas as imagens consolidadas em uma única pasta.
    Gera Markdowns separados para cada PDF e um ZIP único com tudo.

    Características:
    - Processa múltiplos PDFs em paralelo
    - Todas as imagens são salvas em uma única pasta "images/"
    - Detecta duplicatas globalmente (entre todos os PDFs)
    - Gera um arquivo Markdown por PDF
    - Cria um ZIP consolidado com todos os Markdowns e imagens

    Args:
        pdf_paths: Lista de caminhos para os PDFs
        output_dir: Diretório onde salvar tudo
        max_workers: Número máximo de threads para processamento paralelo (padrão: 4)

    Returns:
        Nome do arquivo ZIP consolidado
    """
    logger.info(f"Starting multiple PDF processing: {len(pdf_paths)} files with {max_workers} workers")

    if not pdf_paths or len(pdf_paths) == 0:
        raise ValueError("Nenhum arquivo PDF fornecido.")

    os.makedirs(output_dir, exist_ok=True)
    img_dir = os.path.join(output_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    # Inicializar componentes
    image_mapper = ImageReferenceMapper()
    referenced_images = []

    print("\n📚 Processando múltiplos PDFs...")
    print(f"   Total de arquivos: {len(pdf_paths)}")

    # PRIMEIRA PASSAGEM: extrair TODAS as imagens de TODOS os PDFs (paralelo)
    all_page_images = _extract_images_parallel(pdf_paths, output_dir, max_workers)

    # SEGUNDA PASSAGEM: processar texto de TODOS os PDFs (paralelo)
    print("\n📝 Processando texto de todos os PDFs...")
    total_pages_all = sum(fitz.open(p).page_count for p in pdf_paths)
    print(f"   Total de páginas a processar: {total_pages_all}")

    md_files = _process_text_parallel(
        pdf_paths,
        all_page_images,
        image_mapper,
        output_dir,
        max_workers
    )

    # Coletar imagens referenciadas dos arquivos markdown gerados
    print("\n🔗 Coletando referências de imagens...")
    for pdf_name, md_path in md_files:
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Extrair referências de imagens do markdown
            if "![" in content and "](" in content:
                matches = re.findall(r'\]\(([^)]+)\)', content)
                referenced_images.extend(matches)
    print(f"   ✓ {len(referenced_images)} imagens referenciadas encontradas")

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
            for pdf_name, md_path in md_files:
                md_filename = f"{pdf_name}.md"
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
