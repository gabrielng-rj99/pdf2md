"""
Módulo de limpeza e reconstrução de texto extraído de PDF.

Este módulo lida com problemas comuns de extração de PDF:
- Fórmulas fragmentadas
- Texto quebrado em múltiplas linhas
- Artefatos de paginação
- Sequências de símbolos matemáticos desorganizados
"""

import re
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum


class TextType(Enum):
    """Tipos de texto detectados."""
    NORMAL = "normal"
    FORMULA = "formula"
    FORMULA_FRAGMENT = "formula_fragment"
    HEADER_FOOTER = "header_footer"
    PAGE_NUMBER = "page_number"
    LIST_ITEM = "list_item"


@dataclass
class TextSegment:
    """Segmento de texto com metadados."""
    text: str
    text_type: TextType
    confidence: float = 1.0
    original_text: str = ""


class PDFTextCleaner:
    """
    Limpa e reconstrói texto extraído de PDF.

    Foca especialmente em:
    - Detectar e marcar fórmulas fragmentadas
    - Remover artefatos de paginação
    - Reconstruir texto quebrado
    - Converter caracteres de fontes Symbol/Wingdings
    """

    # Padrões de símbolos matemáticos comuns
    MATH_SYMBOLS = set('αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ∞∑∏∫∂∇√±×÷≤≥≠≈∈∉⊂⊃∪∩')
    MATH_OPERATORS = set('+-*/=<>≤≥≠≈∝∞')

    # Mapeamento de caracteres Private Use Area (PUA) de fontes Symbol/Wingdings
    # Esses caracteres aparecem quando o PDF usa fontes especiais para símbolos
    PUA_MAPPING = {
        # Letras gregas minúsculas (fonte Symbol)
        '\uf061': 'α',  # alpha
        '\uf062': 'β',  # beta
        '\uf063': 'χ',  # chi
        '\uf064': 'δ',  # delta
        '\uf065': 'ε',  # epsilon
        '\uf066': 'φ',  # phi
        '\uf067': 'γ',  # gamma
        '\uf068': 'η',  # eta
        '\uf069': 'ι',  # iota
        '\uf06a': 'ϕ',  # phi variante
        '\uf06b': 'κ',  # kappa
        '\uf06c': 'λ',  # lambda
        '\uf06d': 'μ',  # mu
        '\uf06e': 'ν',  # nu
        '\uf06f': 'ο',  # omicron
        '\uf070': 'π',  # pi
        '\uf071': 'θ',  # theta
        '\uf072': 'ρ',  # rho
        '\uf073': 'σ',  # sigma
        '\uf074': 'τ',  # tau
        '\uf075': 'υ',  # upsilon
        '\uf076': 'ϖ',  # pi variante
        '\uf077': 'ω',  # omega
        '\uf078': 'ξ',  # xi
        '\uf079': 'ψ',  # psi
        '\uf07a': 'ζ',  # zeta

        # Letras gregas maiúsculas (fonte Symbol)
        '\uf041': 'Α',  # Alpha
        '\uf042': 'Β',  # Beta
        '\uf043': 'Χ',  # Chi
        '\uf044': 'Δ',  # Delta
        '\uf045': 'Ε',  # Epsilon
        '\uf046': 'Φ',  # Phi
        '\uf047': 'Γ',  # Gamma
        '\uf048': 'Η',  # Eta
        '\uf049': 'Ι',  # Iota
        '\uf04a': 'ϑ',  # theta variante
        '\uf04b': 'Κ',  # Kappa
        '\uf04c': 'Λ',  # Lambda
        '\uf04d': 'Μ',  # Mu
        '\uf04e': 'Ν',  # Nu
        '\uf04f': 'Ο',  # Omicron
        '\uf050': 'Π',  # Pi
        '\uf051': 'Θ',  # Theta
        '\uf052': 'Ρ',  # Rho
        '\uf053': 'Σ',  # Sigma
        '\uf054': 'Τ',  # Tau
        '\uf055': 'Υ',  # Upsilon
        '\uf056': 'ς',  # sigma final
        '\uf057': 'Ω',  # Omega
        '\uf058': 'Ξ',  # Xi
        '\uf059': 'Ψ',  # Psi
        '\uf05a': 'Ζ',  # Zeta

        # Operadores e símbolos matemáticos
        '\uf020': ' ',  # espaço
        '\uf021': '!',  # exclamação
        '\uf022': '∀',  # para todo
        '\uf023': '#',  # hash
        '\uf024': '∃',  # existe
        '\uf025': '%',  # porcentagem
        '\uf026': '&',  # e comercial
        '\uf027': '∋',  # contém
        '\uf028': '(',  # parêntese esquerdo
        '\uf029': ')',  # parêntese direito
        '\uf02a': '∗',  # asterisco (multiplicação)
        '\uf02b': '+',  # mais
        '\uf02c': ',',  # vírgula
        '\uf02d': '−',  # menos (hífen matemático)
        '\uf02e': '.',  # ponto
        '\uf02f': '/',  # divisão
        '\uf03a': ':',  # dois pontos
        '\uf03b': ';',  # ponto e vírgula
        '\uf03c': '<',  # menor que
        '\uf03d': '=',  # igual
        '\uf03e': '>',  # maior que
        '\uf03f': '?',  # interrogação
        '\uf040': '≅',  # aproximadamente igual

        # Símbolos especiais
        '\uf05b': '[',  # colchete esquerdo
        '\uf05c': '∴',  # portanto
        '\uf05d': ']',  # colchete direito
        '\uf05e': '⊥',  # perpendicular
        '\uf05f': '_',  # underscore
        '\uf060': '‾',  # overline

        # Símbolos matemáticos avançados
        '\uf0a3': '≤',  # menor ou igual
        '\uf0a5': '∞',  # infinito
        '\uf0ae': '→',  # seta direita
        '\uf0af': '←',  # seta esquerda
        '\uf0ab': '↔',  # seta dupla
        '\uf0ad': '↓',  # seta baixo
        '\uf0ac': '↑',  # seta cima
        '\uf0b3': '≥',  # maior ou igual
        '\uf0b4': '×',  # multiplicação
        '\uf0b5': '∝',  # proporcional
        '\uf0b6': '∂',  # derivada parcial
        '\uf0b7': '•',  # bullet
        '\uf0b8': '÷',  # divisão
        '\uf0b9': '≠',  # diferente
        '\uf0ba': '≡',  # identicamente igual
        '\uf0bb': '≈',  # aproximadamente
        '\uf0bc': '…',  # reticências
        '\uf0bd': '|',  # barra vertical
        '\uf0be': '─',  # linha horizontal
        '\uf0bf': '↵',  # enter/retorno

        # Integrais e somatórios
        '\uf0e5': '∂',  # derivada parcial
        '\uf0f2': '∫',  # integral
        '\uf0e4': '⊗',  # produto tensorial
        '\uf0c5': '∏',  # produtório
        '\uf0e5': '∑',  # somatório (alternativo)

        # Implicações e lógica
        '\uf0d0': '°',  # grau
        '\uf0d1': '⇐',  # implica (esquerda)
        '\uf0de': '⇒',  # implica (direita)
        '\uf0db': '⇔',  # se e somente se

        # Símbolos de conjuntos
        '\uf0c7': '∩',  # interseção
        '\uf0c8': '∪',  # união
        '\uf0c9': '⊃',  # contém (superconjunto)
        '\uf0ca': '⊇',  # contém ou igual
        '\uf0cb': '⊄',  # não é subconjunto
        '\uf0cc': '⊂',  # subconjunto
        '\uf0cd': '⊆',  # subconjunto ou igual
        '\uf0ce': '∈',  # pertence
        '\uf0cf': '∉',  # não pertence

        # Raiz e outros
        '\uf0d6': '√',  # raiz quadrada
        '\uf0d7': '∛',  # raiz cúbica

        # Wingdings checkmarks e símbolos
        '\uf0fc': '✓',  # checkmark (Wingdings)
        '\uf0fb': '✗',  # x mark
        '\uf0fe': '☐',  # checkbox vazio
        '\uf076': '✔',  # checkmark alternativo
        '\uf06f': '●',  # bullet cheio
        '\uf0a7': '■',  # quadrado cheio
        '\uf0a8': '□',  # quadrado vazio
        '\uf0b7': '•',  # bullet pequeno
    }

    # Padrões regex para detecção
    PATTERNS = {
        # Número de página puro
        'page_number': re.compile(r'^\s*\d{1,4}\s*$'),

        # Número de página com texto
        'page_with_text': re.compile(r'(página|page|pág\.?)\s*\d+', re.IGNORECASE),

        # Código de documento (ex: HSN002)
        'doc_code': re.compile(r'^[A-Z]{2,}\d{2,}'),

        # Fração no formato a/b ou a÷b
        'fraction': re.compile(r'\b\d+\s*[/÷]\s*\d+\b'),

        # Potência no formato x^n ou x² etc
        'power': re.compile(r'[\w\d]\s*[\^²³⁴⁵⁶⁷⁸⁹]'),

        # Subscrito no formato x_n ou H₂O
        'subscript': re.compile(r'[\w]\s*[_₀₁₂₃₄₅₆₇₈₉]'),

        # Equação com igual
        'equation': re.compile(r'[=≈≠<>≤≥]'),

        # Letras gregas escritas por extenso
        'greek_word': re.compile(r'\b(alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|lambda|mu|nu|xi|omicron|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega|rho|gamma)\b', re.IGNORECASE),

        # Função matemática
        'math_function': re.compile(r'\b(sen|cos|tan|log|ln|exp|sin|tg|ctg|sec|csc|arcsen|arccos|arctan|sinh|cosh|tanh|lim|max|min|sup|inf)\b', re.IGNORECASE),

        # Unidades de medida
        'units': re.compile(r'\b(kg|m|s|N|Pa|J|W|Hz|mol|K|A|cd|rad|sr|kgf|cm|mm|km|g|mg|kPa|MPa|GPa)\b(?:/[²³]?|\^[0-9-]+)?'),

        # Variáveis comuns em física/engenharia
        'physics_vars': re.compile(r'\b[VPTRFAME](?:\s*[=:]|\s+[a-z])'),

        # Sequência que parece fórmula fragmentada
        # Ex: "volume V massa m sendo V m ρ"
        'fragmented_formula': re.compile(r'(?:\b[a-zA-Z]\s+){2,}(?:[=:]|sendo)'),

        # Número de equação entre parênteses
        'equation_number': re.compile(r'\(\s*\d+\.\d+\s*\)'),
    }

    def __init__(self):
        """Inicializa o limpador de texto."""
        self._header_patterns: List[str] = []
        self._seen_texts: Dict[str, int] = {}

    def clean_text(self, text: str) -> str:
        """
        Limpa texto de artefatos de PDF.

        Args:
            text: Texto bruto extraído do PDF

        Returns:
            Texto limpo
        """
        if not text:
            return ""

        # 1. Converter caracteres PUA (Symbol/Wingdings) para Unicode padrão
        text = self._convert_pua_chars(text)

        # 2. Remover artefatos de número de página incorporado
        text = self._remove_page_number_artifacts(text)

        # 3. Normalizar espaços
        text = self._normalize_whitespace(text)

        # 4. Limpar caracteres de controle
        text = self._remove_control_chars(text)

        return text.strip()

    def _convert_pua_chars(self, text: str) -> str:
        """
        Converte caracteres da Private Use Area (PUA) para Unicode padrão.

        Esses caracteres vêm de fontes como Symbol, Wingdings, etc.

        Args:
            text: Texto com possíveis caracteres PUA

        Returns:
            Texto com caracteres convertidos
        """
        if not text:
            return text

        result = []
        for char in text:
            if char in self.PUA_MAPPING:
                result.append(self.PUA_MAPPING[char])
            else:
                # Remover outros caracteres PUA não mapeados (U+E000 a U+F8FF)
                code = ord(char)
                if 0xE000 <= code <= 0xF8FF:
                    # Substituir por espaço para não quebrar palavras
                    result.append(' ')
                else:
                    result.append(char)

        return ''.join(result)

    def _remove_page_number_artifacts(self, text: str) -> str:
        """Remove números de página incorporados ao texto."""

        # Padrão: $NUMERO LETRA$ (número de página do PDF)
        # Ex: "$3 C$omo" -> "Como"
        text = re.sub(r'\$(\d{1,3})\s*([A-ZÀ-Úa-zà-ú][a-zà-ú]*)\$', r'\2', text)

        # Padrão: $NUMERO$ isolado
        text = re.sub(r'\$\d{1,3}\$', '', text)

        # Número de página no início seguido de letra maiúscula
        text = re.sub(r'^(\d{1,3})\s+([A-ZÀ-Ú])', r'\2', text)

        # Número de página no final após espaços múltiplos
        text = re.sub(r'\s{2,}\d{1,3}\s*$', '', text)

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normaliza espaços em branco."""
        # Múltiplos espaços -> dois espaços (preserva alguma estrutura)
        text = re.sub(r' {3,}', '  ', text)
        # Tabs -> espaços
        text = re.sub(r'\t+', ' ', text)
        # Espaços no início e fim de linha
        text = re.sub(r'^ +| +$', '', text, flags=re.MULTILINE)
        return text

    def _remove_control_chars(self, text: str) -> str:
        """Remove caracteres de controle exceto newline e tab."""
        return ''.join(c for c in text if c == '\n' or c == '\t' or (ord(c) >= 32 and ord(c) != 127))

    def classify_text(self, text: str) -> TextType:
        """
        Classifica o tipo de texto.

        Args:
            text: Texto a classificar

        Returns:
            Tipo do texto
        """
        text_clean = text.strip()

        if not text_clean:
            return TextType.NORMAL

        # Número de página puro
        if self.PATTERNS['page_number'].match(text_clean):
            return TextType.PAGE_NUMBER

        # Header/footer detectado por padrões
        if self._is_header_footer(text_clean):
            return TextType.HEADER_FOOTER

        # Fórmula completa ou fragmentada
        formula_score = self._calculate_formula_score(text_clean)
        if formula_score > 0.7:
            return TextType.FORMULA
        elif formula_score > 0.4:
            return TextType.FORMULA_FRAGMENT

        # Item de lista
        if re.match(r'^[\d\-•◦▪→]\s', text_clean):
            return TextType.LIST_ITEM

        return TextType.NORMAL

    def _is_header_footer(self, text: str) -> bool:
        """Verifica se o texto é header ou footer."""

        # Código de documento no início
        if self.PATTERNS['doc_code'].match(text):
            return True

        # Página X de Y
        if self.PATTERNS['page_with_text'].search(text):
            return True

        # Texto muito longo com múltiplos espaços (característico de header)
        if len(text) > 80 and text.count('  ') >= 2:
            return True

        # Padrões institucionais
        institutional = [
            r'universidade\s+(federal|estadual)',
            r'faculdade\s+de',
            r'instituto\s+(federal|de)',
            r'©\s*\d{4}',
        ]
        for pattern in institutional:
            if re.search(pattern, text, re.IGNORECASE):
                if len(text) < 150:
                    return True

        return False

    def _calculate_formula_score(self, text: str) -> float:
        """
        Calcula uma pontuação de 0-1 indicando probabilidade de ser fórmula.

        Args:
            text: Texto a analisar

        Returns:
            Score de 0 a 1
        """
        if not text or len(text) < 2:
            return 0.0

        score = 0.0
        factors = 0

        # Símbolos matemáticos
        math_symbol_count = sum(1 for c in text if c in self.MATH_SYMBOLS)
        if math_symbol_count > 0:
            score += min(0.3, math_symbol_count * 0.1)
            factors += 1

        # Operadores
        operator_count = sum(1 for c in text if c in self.MATH_OPERATORS)
        if operator_count > 0:
            score += min(0.2, operator_count * 0.05)
            factors += 1

        # Frações
        if self.PATTERNS['fraction'].search(text):
            score += 0.3
            factors += 1

        # Potências
        if self.PATTERNS['power'].search(text):
            score += 0.25
            factors += 1

        # Subscritos
        if self.PATTERNS['subscript'].search(text):
            score += 0.2
            factors += 1

        # Equação
        if self.PATTERNS['equation'].search(text):
            score += 0.2
            factors += 1

        # Letras gregas
        if self.PATTERNS['greek_word'].search(text):
            score += 0.25
            factors += 1

        # Funções matemáticas
        if self.PATTERNS['math_function'].search(text):
            score += 0.3
            factors += 1

        # Número de equação
        if self.PATTERNS['equation_number'].search(text):
            score += 0.4
            factors += 1

        # Fórmula fragmentada (padrão típico)
        if self.PATTERNS['fragmented_formula'].search(text):
            score += 0.35
            factors += 1

        # Proporção de letras isoladas (típico de variáveis)
        isolated_letters = len(re.findall(r'\b[A-Za-z]\b', text))
        if isolated_letters > 2:
            score += min(0.2, isolated_letters * 0.03)
            factors += 1

        # Normalizar
        if factors > 0:
            return min(1.0, score)

        return 0.0

    def detect_formula_regions(self, text: str) -> List[Tuple[int, int, float]]:
        """
        Detecta regiões do texto que parecem ser fórmulas.

        Args:
            text: Texto completo

        Returns:
            Lista de (início, fim, confiança) para cada região de fórmula
        """
        regions = []

        # Detectar por padrões específicos
        patterns_to_check = [
            (self.PATTERNS['equation_number'], 0.9),
            (self.PATTERNS['fraction'], 0.7),
            (self.PATTERNS['power'], 0.6),
            (self.PATTERNS['math_function'], 0.7),
        ]

        for pattern, confidence in patterns_to_check:
            for match in pattern.finditer(text):
                # Expandir região para incluir contexto
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)

                # Ajustar para limites de palavra
                while start > 0 and text[start] not in ' \n\t':
                    start -= 1
                while end < len(text) and text[end] not in ' \n\t':
                    end += 1

                regions.append((start, end, confidence))

        # Mesclar regiões sobrepostas
        regions = self._merge_regions(regions)

        return regions

    def _merge_regions(self, regions: List[Tuple[int, int, float]]) -> List[Tuple[int, int, float]]:
        """Mescla regiões sobrepostas."""
        if not regions:
            return []

        # Ordenar por início
        regions = sorted(regions, key=lambda x: x[0])

        merged = [regions[0]]
        for start, end, conf in regions[1:]:
            last_start, last_end, last_conf = merged[-1]

            # Se sobrepõe, mesclar
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end), max(last_conf, conf))
            else:
                merged.append((start, end, conf))

        return merged

    def reconstruct_formula(self, fragments: List[str]) -> str:
        """
        Tenta reconstruir uma fórmula a partir de fragmentos.

        Args:
            fragments: Lista de fragmentos de texto que compõem a fórmula

        Returns:
            Fórmula reconstruída (ou texto original se não for possível)
        """
        if not fragments:
            return ""

        if len(fragments) == 1:
            return fragments[0]

        # Juntar fragmentos
        combined = ' '.join(fragments)

        # Tentar identificar estrutura
        # Padrão: "variável = expressão"
        eq_match = re.search(r'([A-Za-z_]\w*)\s*[=:]\s*(.+)', combined)
        if eq_match:
            var, expr = eq_match.groups()
            return f"{var} = {expr.strip()}"

        # Padrão: fração "numerador / denominador" ou "num sobre denom"
        frac_match = re.search(r'(\S+)\s*[/÷]\s*(\S+)', combined)
        if frac_match:
            num, denom = frac_match.groups()
            return f"\\frac{{{num}}}{{{denom}}}"

        return combined

    def extract_equation_label(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Extrai o rótulo de equação do texto.

        Args:
            text: Texto que pode conter rótulo de equação

        Returns:
            Tupla (texto_sem_rótulo, rótulo ou None)
        """
        # Padrão: (X.Y) no final
        match = re.search(r'\s*\((\d+\.\d+)\)\s*$', text)
        if match:
            label = match.group(1)
            text_clean = text[:match.start()].strip()
            return text_clean, label

        return text, None

    def is_likely_formula_continuation(self, prev_text: str, curr_text: str) -> bool:
        """
        Verifica se o texto atual é provavelmente continuação de fórmula.

        Args:
            prev_text: Texto anterior
            curr_text: Texto atual

        Returns:
            True se parece ser continuação
        """
        if not prev_text or not curr_text:
            return False

        prev_clean = prev_text.strip()
        curr_clean = curr_text.strip()

        # Se anterior termina com operador
        if prev_clean and prev_clean[-1] in '+-*/=<>':
            return True

        # Se atual começa com operador
        if curr_clean and curr_clean[0] in '+-*/=<>':
            return True

        # Se anterior tem fórmula parcial e atual parece ser continuação
        prev_score = self._calculate_formula_score(prev_clean)
        curr_score = self._calculate_formula_score(curr_clean)

        if prev_score > 0.5 and curr_score > 0.3:
            return True

        return False


class FormulaReconstructor:
    """
    Reconstrói fórmulas fragmentadas em LaTeX válido.
    """

    # Mapeamento de texto para LaTeX
    LATEX_MAP = {
        # Letras gregas
        'alpha': r'\alpha', 'beta': r'\beta', 'gamma': r'\gamma',
        'delta': r'\delta', 'epsilon': r'\epsilon', 'zeta': r'\zeta',
        'eta': r'\eta', 'theta': r'\theta', 'iota': r'\iota',
        'kappa': r'\kappa', 'lambda': r'\lambda', 'mu': r'\mu',
        'nu': r'\nu', 'xi': r'\xi', 'pi': r'\pi',
        'rho': r'\rho', 'sigma': r'\sigma', 'tau': r'\tau',
        'upsilon': r'\upsilon', 'phi': r'\phi', 'chi': r'\chi',
        'psi': r'\psi', 'omega': r'\omega',
        # Maiúsculas
        'Alpha': r'\Alpha', 'Beta': r'\Beta', 'Gamma': r'\Gamma',
        'Delta': r'\Delta', 'Epsilon': r'\Epsilon', 'Zeta': r'\Zeta',
        'Eta': r'\Eta', 'Theta': r'\Theta', 'Iota': r'\Iota',
        'Kappa': r'\Kappa', 'Lambda': r'\Lambda', 'Mu': r'\Mu',
        'Nu': r'\Nu', 'Xi': r'\Xi', 'Pi': r'\Pi',
        'Rho': r'\Rho', 'Sigma': r'\Sigma', 'Tau': r'\Tau',
        'Upsilon': r'\Upsilon', 'Phi': r'\Phi', 'Chi': r'\Chi',
        'Psi': r'\Psi', 'Omega': r'\Omega',
        # Símbolos
        '∞': r'\infty', '∑': r'\sum', '∏': r'\prod',
        '∫': r'\int', '∂': r'\partial', '∇': r'\nabla',
        '√': r'\sqrt', '±': r'\pm', '×': r'\times',
        '÷': r'\div', '≤': r'\leq', '≥': r'\geq',
        '≠': r'\neq', '≈': r'\approx', '∈': r'\in',
        '∉': r'\notin', '⊂': r'\subset', '⊃': r'\supset',
        '∪': r'\cup', '∩': r'\cap', '→': r'\rightarrow',
        '←': r'\leftarrow', '↔': r'\leftrightarrow',
        # Funções
        'sen': r'\sin', 'cos': r'\cos', 'tan': r'\tan',
        'tg': r'\tan', 'log': r'\log', 'ln': r'\ln',
        'exp': r'\exp', 'lim': r'\lim', 'max': r'\max',
        'min': r'\min',
    }

    # Subscritos Unicode para número
    SUBSCRIPT_MAP = {
        '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
        '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
    }

    # Superscritos Unicode para número
    SUPERSCRIPT_MAP = {
        '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
        '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
    }

    def __init__(self):
        """Inicializa o reconstrutor."""
        pass

    def text_to_latex(self, text: str) -> str:
        """
        Converte texto com notação matemática para LaTeX.

        Args:
            text: Texto com fórmula

        Returns:
            Texto convertido para LaTeX
        """
        if not text:
            return ""

        result = text

        # Substituir símbolos conhecidos
        for symbol, latex in self.LATEX_MAP.items():
            result = re.sub(r'\b' + re.escape(symbol) + r'\b', latex, result, flags=re.IGNORECASE)

        # Converter subscritos Unicode
        for sub, num in self.SUBSCRIPT_MAP.items():
            result = result.replace(sub, f'_{{{num}}}')

        # Converter superscritos Unicode
        for sup, num in self.SUPERSCRIPT_MAP.items():
            result = result.replace(sup, f'^{{{num}}}')

        # Converter frações simples a/b -> \frac{a}{b}
        result = re.sub(r'(\d+|\w)\s*/\s*(\d+|\w)', r'\\frac{\1}{\2}', result)

        # Converter potências x^2 -> x^{2}
        result = re.sub(r'\^(\d+)', r'^{\1}', result)

        # Converter subscritos x_2 -> x_{2}
        result = re.sub(r'_(\d+)', r'_{\1}', result)

        return result

    def wrap_inline(self, formula: str) -> str:
        """Envolve fórmula em delimitadores inline."""
        return f'${formula}$'

    def wrap_block(self, formula: str) -> str:
        """Envolve fórmula em delimitadores de bloco."""
        return f'$$\n{formula}\n$$'

    def format_equation(self, text: str, label: Optional[str] = None) -> str:
        """
        Formata uma equação completa.

        Args:
            text: Texto da equação
            label: Rótulo opcional (ex: "1.1")

        Returns:
            Equação formatada em LaTeX
        """
        latex = self.text_to_latex(text)

        if label:
            return f'$${latex} \\quad ({label})$$'
        else:
            return f'$${latex}$$'


def clean_pdf_text(text: str) -> str:
    """
    Função de conveniência para limpar texto de PDF.

    Args:
        text: Texto bruto do PDF

    Returns:
        Texto limpo
    """
    cleaner = PDFTextCleaner()
    return cleaner.clean_text(text)


def classify_text_type(text: str) -> TextType:
    """
    Função de conveniência para classificar tipo de texto.

    Args:
        text: Texto a classificar

    Returns:
        Tipo do texto
    """
    cleaner = PDFTextCleaner()
    return cleaner.classify_text(text)
