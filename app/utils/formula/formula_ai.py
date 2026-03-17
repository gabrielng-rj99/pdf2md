"""
Módulo de IA leve para reconhecimento e reconstrução de fórmulas matemáticas.

Este módulo usa uma abordagem híbrida:
1. Classificador baseado em features (rápido, sem dependências pesadas)
2. Regras heurísticas para reconstrução de fórmulas fragmentadas
3. Conversão inteligente para LaTeX
4. Uso de contexto imediato (texto anterior/posterior) para identificar fórmulas

Otimizado para ser rápido e leve (< 1MB de memória adicional).
Não usa APIs externas - tudo é processado localmente.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple, Optional, Dict, Set
import math


class FormulaConfidence(Enum):
    """Níveis de confiança na detecção de fórmula."""
    NONE = 0        # Não é fórmula
    LOW = 1         # Possivelmente fórmula
    MEDIUM = 2      # Provavelmente fórmula
    HIGH = 3        # Certamente fórmula


@dataclass
class FormulaFeatures:
    """Características extraídas de um texto para classificação."""
    # Contagens
    total_chars: int = 0
    total_words: int = 0
    isolated_letters: int = 0          # Letras isoladas (variáveis)
    math_symbols: int = 0              # Símbolos matemáticos
    greek_letters: int = 0             # Letras gregas
    operators: int = 0                 # Operadores +, -, *, /, =
    numbers: int = 0                   # Números
    subscripts: int = 0                # Subscritos
    superscripts: int = 0              # Superscritos
    parentheses: int = 0               # Parênteses

    # Proporções
    symbol_ratio: float = 0.0          # Proporção de símbolos
    letter_ratio: float = 0.0          # Proporção de letras isoladas

    # Padrões detectados
    has_equation: bool = False         # Tem sinal de =
    has_fraction: bool = False         # Tem fração (/)
    has_power: bool = False            # Tem potência (^, ², ³)
    has_function: bool = False         # Tem função (sen, cos, log)
    has_equation_number: bool = False  # Tem número de equação (X.Y)
    has_units: bool = False            # Tem unidades de medida

    # Contexto
    starts_with_connector: bool = False  # Começa com "onde", "sendo"
    ends_with_connector: bool = False    # Termina com "onde", "sendo"

    # Score final
    formula_score: float = 0.0


@dataclass
class ReconstructedFormula:
    """Fórmula reconstruída."""
    original: str
    latex: str
    confidence: FormulaConfidence
    equation_label: Optional[str] = None
    description: str = ""
    formula_name: Optional[str] = None  # Nome da fórmula detectado pelo contexto
    context_hint: Optional[str] = None  # Dica extraída do contexto


@dataclass
class FormulaContext:
    """Contexto imediato de uma fórmula."""
    text_before: str = ""  # Texto que vem antes da fórmula
    text_after: str = ""   # Texto que vem depois da fórmula
    detected_name: Optional[str] = None  # Nome detectado (ex: "massa específica")
    detected_type: Optional[str] = None  # Tipo (ex: "definição", "equação", "lei")
    context_hint: Optional[str] = None  # Dica de contexto adicional
    related_variables: List[str] = field(default_factory=list)  # Variáveis mencionadas


class LightFormulaAI:
    """
    IA leve para detecção e reconstrução de fórmulas matemáticas.

    Usa classificação baseada em features + regras heurísticas + contexto imediato.
    Extremamente rápido e com baixo consumo de memória.
    Não depende de APIs externas.
    """

    # Símbolos matemáticos Unicode
    MATH_SYMBOLS: Set[str] = set(
        '∞∑∏∫∬∭∮∂∇√∛∜±∓×÷·∘∙≤≥≠≈≡≢∝∈∉⊂⊃⊆⊇∪∩∧∨¬→←↔⇒⇐⇔∀∃∄∅∴∵'
        '⟨⟩⌈⌉⌊⌋‖∥∦∠∡∢△▽□◇○●◦'
    )

    # Letras gregas
    GREEK_LETTERS: Set[str] = set(
        'αβγδεζηθικλμνξοπρσςτυφχψω'
        'ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ'
    )

    # Operadores básicos
    OPERATORS: Set[str] = set('+-*/=<>≤≥≠≈')

    # Subscritos e superscritos Unicode
    SUBSCRIPTS: Set[str] = set('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₔₕₖₗₘₙₚₛₜ')
    SUPERSCRIPTS: Set[str] = set('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ')

    # Palavras conectoras em português e inglês
    CONNECTORS: Set[str] = {
        'onde', 'sendo', 'com', 'para', 'que', 'temos', 'logo', 'então',
        'portanto', 'assim', 'dado', 'dados', 'seja', 'sejam',
        'where', 'given', 'with', 'for', 'thus', 'hence', 'therefore'
    }

    # Funções matemáticas
    MATH_FUNCTIONS: Set[str] = {
        'sen', 'cos', 'tan', 'tg', 'ctg', 'sec', 'csc', 'cossec',
        'sin', 'arcsen', 'arccos', 'arctan', 'arctg',
        'sinh', 'cosh', 'tanh', 'senh', 'cosh', 'tgh',
        'log', 'ln', 'lg', 'exp',
        'lim', 'max', 'min', 'sup', 'inf',
        'det', 'tr', 'rank', 'dim',
        'grad', 'div', 'rot', 'curl'
    }

    # Unidades de medida comuns
    UNITS: Set[str] = {
        # SI base
        'm', 'kg', 's', 'A', 'K', 'mol', 'cd',
        # SI derivadas
        'N', 'Pa', 'J', 'W', 'C', 'V', 'F', 'Ω', 'S', 'Wb', 'T', 'H', 'Hz',
        # Prefixos comuns
        'km', 'cm', 'mm', 'μm', 'nm',
        'kN', 'MN', 'kPa', 'MPa', 'GPa',
        'kJ', 'MJ', 'kW', 'MW',
        # Outras
        'kgf', 'atm', 'bar', 'mbar',
        'L', 'mL', 'dL',
        'rad', 'sr', '°', '°C', '°F',
    }

    # Padrões regex compilados (para performance)
    PATTERNS = {
        'isolated_letter': re.compile(r'\b[A-Za-z]\b'),
        'number': re.compile(r'\b\d+(?:[.,]\d+)?\b'),
        'fraction': re.compile(r'\b\w+\s*/\s*\w+\b'),
        'power': re.compile(r'[\w\)]\s*[\^²³⁴⁵⁶⁷⁸⁹]'),
        'subscript': re.compile(r'[\w]\s*[_₀₁₂₃₄₅₆₇₈₉]'),
        'equation_number': re.compile(r'\(?\s*\d+\s*[.,]\s*\d+\s*\)?'),
        'greek_word': re.compile(
            r'\b(alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|'
            r'lambda|mu|nu|xi|omicron|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega)\b',
            re.IGNORECASE
        ),
        'function': re.compile(
            r'\b(sen|cos|tan|tg|log|ln|exp|lim|max|min|sin|sinh|cosh|tanh)\b',
            re.IGNORECASE
        ),
        'unit_pattern': re.compile(
            r'\b(kg|kgf|m|cm|mm|km|s|N|Pa|kPa|MPa|J|W|Hz|mol|K|L|mL|atm|bar)\b'
            r'(?:\s*/\s*(?:m|s|kg))?(?:[²³]|\^[0-9-]+)?',
            re.IGNORECASE
        ),
        # Padrão de fórmula fragmentada típica
        'fragmented': re.compile(r'(?:\b[A-Za-z]\b\s+){3,}'),
        # Padrão de variável = expressão
        'assignment': re.compile(r'\b[A-Za-z_]\w*\s*[=:]\s*\S'),
    }

    # Pesos para cálculo de score (ajustados empiricamente)
    WEIGHTS = {
        'isolated_letters': 0.15,
        'math_symbols': 0.25,
        'greek_letters': 0.20,
        'operators': 0.10,
        'subscripts': 0.15,
        'superscripts': 0.15,
        'has_equation': 0.20,
        'has_fraction': 0.15,
        'has_power': 0.15,
        'has_function': 0.20,
        'has_equation_number': 0.25,
        'fragmented_penalty': -0.30,  # Penalidade para texto muito fragmentado
    }

    # Thresholds - mais conservadores para evitar falsos positivos
    THRESHOLD_LOW = 0.35
    THRESHOLD_MEDIUM = 0.55
    THRESHOLD_HIGH = 0.75

    # ========== SISTEMA DE CONTEXTO ==========

    # Padrões que indicam que uma fórmula está vindo
    FORMULA_INTRO_PATTERNS = [
        # Português
        r'(?:é\s+)?(?:dado|dada|definido|definida)\s+(?:por|como)',
        r'(?:é\s+)?(?:expressa?|representada?|calculada?)\s+(?:por|como)',
        r'(?:pode\s+ser\s+)?(?:escrit[ao]|obtid[ao])\s+(?:como|por)',
        r'temos\s+(?:que|a\s+(?:seguinte\s+)?(?:expressão|equação|fórmula))',
        r'(?:a\s+)?(?:equação|fórmula|expressão|relação)\s+(?:é|será)',
        r'(?:pela|através\s+da)\s+(?:equação|fórmula|expressão)',
        r'(?:segundo|de\s+acordo\s+com)\s+a\s+(?:equação|fórmula)',
        # Inglês
        r'is\s+(?:given|defined|expressed)\s+(?:by|as)',
        r'can\s+be\s+(?:written|obtained|expressed)\s+as',
        r'(?:the\s+)?(?:equation|formula|expression)\s+(?:is|becomes)',
    ]

    # Padrões que indicam o nome/tipo da fórmula
    FORMULA_NAME_PATTERNS = [
        # Definições de grandezas físicas
        (r'(?:a\s+)?massa\s+específica', 'massa específica', 'ρ = m/V'),
        (r'(?:o\s+)?peso\s+específico', 'peso específico', 'γ = ρg'),
        (r'(?:a\s+)?densidade', 'densidade', 'ρ = m/V'),
        (r'(?:a\s+)?pressão', 'pressão', 'P = F/A'),
        (r'(?:a\s+)?viscosidade', 'viscosidade', 'μ'),
        (r'(?:a\s+)?tensão\s+(?:superficial|cisalhante)', 'tensão', 'τ'),
        (r'(?:o\s+)?volume\s+específico', 'volume específico', 'Vs = 1/ρ'),
        (r'(?:a\s+)?compressibilidade', 'compressibilidade', 'β'),
        (r'(?:o\s+)?módulo\s+de\s+elasticidade', 'módulo de elasticidade', 'E'),
        # Leis e equações famosas
        (r'(?:lei|equação)\s+de\s+Stevin', 'Lei de Stevin', 'P = P₀ + ρgh'),
        (r'(?:lei|equação)\s+de\s+Pascal', 'Lei de Pascal', 'P = F/A'),
        (r'(?:lei|equação)\s+de\s+Newton', 'Lei de Newton', 'F = ma'),
        (r'(?:equação\s+)?(?:dos\s+)?gases\s+(?:perfeitos|ideais)', 'Equação dos Gases', 'PV = nRT'),
        (r'(?:equação\s+)?de\s+Bernoulli', 'Equação de Bernoulli', 'P + ρv²/2 + ρgh = const'),
        (r'(?:equação\s+)?da\s+continuidade', 'Equação da Continuidade', 'A₁v₁ = A₂v₂'),
        # Inglês
        (r"Stevin'?s?\s+(?:law|equation)", 'Lei de Stevin', 'P = P₀ + ρgh'),
        (r"Pascal'?s?\s+(?:law|principle)", 'Lei de Pascal', 'P = F/A'),
        (r'ideal\s+gas\s+(?:law|equation)', 'Equação dos Gases', 'PV = nRT'),
    ]

    # Mapeamento de variáveis comuns e seus significados
    KNOWN_VARIABLES = {
        # Letras gregas
        'ρ': ('rho', 'massa específica, densidade'),
        'γ': ('gamma', 'peso específico'),
        'μ': ('mu', 'viscosidade dinâmica'),
        'ν': ('nu', 'viscosidade cinemática'),
        'τ': ('tau', 'tensão cisalhante'),
        'σ': ('sigma', 'tensão normal'),
        'ε': ('epsilon', 'deformação'),
        'θ': ('theta', 'ângulo'),
        'π': ('pi', 'constante pi'),
        'Δ': ('delta', 'variação'),
        # Latinas comuns
        'P': ('P', 'pressão'),
        'V': ('V', 'volume'),
        'T': ('T', 'temperatura'),
        'F': ('F', 'força'),
        'A': ('A', 'área'),
        'm': ('m', 'massa'),
        'g': ('g', 'aceleração da gravidade'),
        'h': ('h', 'altura'),
        'v': ('v', 'velocidade'),
        'R': ('R', 'constante dos gases'),
        'n': ('n', 'número de moles'),
        'E': ('E', 'módulo de elasticidade'),
    }

    # Fórmulas conhecidas e suas reconstruções
    KNOWN_FORMULAS = {
        # Padrões fragmentados -> reconstrução correta
        'massa volume sendo': r'\rho = \frac{m}{V}',
        'volume massa sendo': r'\rho = \frac{m}{V}',
        'peso volume sendo': r'\gamma = \frac{W}{V}',
        'volume peso sendo': r'\gamma = \frac{W}{V}',
        'força área sendo': r'P = \frac{F}{A}',
        'área força sendo': r'P = \frac{F}{A}',
        'pressão altura': r'P = \rho g h',
        'viscosidade dinâmica': r'\mu',
        'viscosidade cinemática': r'\nu = \frac{\mu}{\rho}',
        'módulo compressibilidade': r'\beta = -\frac{1}{V}\frac{dV}{dP}',
        'gases perfeitos': r'PV = nRT',
        'nrt pv': r'PV = nRT',
    }

    def __init__(self):
        """Inicializa o classificador."""
        # Cache para features já calculadas
        self._cache: Dict[str, FormulaFeatures] = {}
        self._cache_max_size = 1000
        # Compilar padrões de contexto
        self._intro_patterns = [re.compile(p, re.IGNORECASE) for p in self.FORMULA_INTRO_PATTERNS]
        self._name_patterns = [(re.compile(p, re.IGNORECASE), name, hint)
                               for p, name, hint in self.FORMULA_NAME_PATTERNS]

    def extract_features(self, text: str) -> FormulaFeatures:
        """
        Extrai características do texto para classificação.

        Args:
            text: Texto a analisar

        Returns:
            FormulaFeatures com todas as características extraídas
        """
        # Verificar cache
        cache_key = text[:100]  # Usar primeiros 100 chars como chave
        if cache_key in self._cache:
            return self._cache[cache_key]

        features = FormulaFeatures()

        if not text:
            return features

        # Contagens básicas
        features.total_chars = len(text)
        features.total_words = len(text.split())

        # Contar elementos
        for char in text:
            if char in self.MATH_SYMBOLS:
                features.math_symbols += 1
            elif char in self.GREEK_LETTERS:
                features.greek_letters += 1
            elif char in self.OPERATORS:
                features.operators += 1
            elif char in self.SUBSCRIPTS:
                features.subscripts += 1
            elif char in self.SUPERSCRIPTS:
                features.superscripts += 1
            elif char in '()[]{}':
                features.parentheses += 1

        # Contar padrões via regex
        features.isolated_letters = len(self.PATTERNS['isolated_letter'].findall(text))
        features.numbers = len(self.PATTERNS['number'].findall(text))

        # Detectar padrões booleanos
        features.has_equation = '=' in text or '≈' in text or '≠' in text
        features.has_fraction = bool(self.PATTERNS['fraction'].search(text))
        features.has_power = bool(self.PATTERNS['power'].search(text))
        features.has_function = bool(self.PATTERNS['function'].search(text))
        features.has_equation_number = bool(self.PATTERNS['equation_number'].search(text))
        features.has_units = bool(self.PATTERNS['unit_pattern'].search(text))

        # Detectar letras gregas por nome
        if self.PATTERNS['greek_word'].search(text):
            features.greek_letters += 1

        # Detectar contexto
        words = text.lower().split()
        if words:
            features.starts_with_connector = words[0] in self.CONNECTORS
            features.ends_with_connector = words[-1] in self.CONNECTORS

        # Calcular proporções
        if features.total_chars > 0:
            total_special = (features.math_symbols + features.greek_letters +
                          features.operators + features.subscripts + features.superscripts)
            features.symbol_ratio = total_special / features.total_chars
            features.letter_ratio = features.isolated_letters / max(1, features.total_words)

        # Calcular score final
        features.formula_score = self._calculate_score(features, text)

        # Adicionar ao cache
        if len(self._cache) < self._cache_max_size:
            self._cache[cache_key] = features

        return features

    def _calculate_score(self, features: FormulaFeatures, text: str) -> float:
        """
        Calcula o score de probabilidade de ser fórmula.

        Args:
            features: Características extraídas
            text: Texto original

        Returns:
            Score de 0.0 a 1.0
        """
        score = 0.0

        # Penalidade para textos longos (provavelmente parágrafos, não fórmulas)
        if features.total_chars > 200:
            score -= 0.3
        elif features.total_chars > 100:
            score -= 0.15

        # Pontuação baseada em contagens (normalizada)
        # Requer mais evidência para textos maiores
        min_isolated = 3 if features.total_chars > 50 else 2
        if features.isolated_letters >= min_isolated:
            score += self.WEIGHTS['isolated_letters'] * min(1.0, features.isolated_letters / 6)

        if features.math_symbols >= 2:
            score += self.WEIGHTS['math_symbols'] * min(1.0, features.math_symbols / 4)

        if features.greek_letters >= 1:
            score += self.WEIGHTS['greek_letters'] * min(1.0, features.greek_letters / 2)

        if features.operators >= 2:
            score += self.WEIGHTS['operators'] * min(1.0, features.operators / 4)

        if features.subscripts >= 1:
            score += self.WEIGHTS['subscripts'] * min(1.0, features.subscripts / 2)

        if features.superscripts >= 1:
            score += self.WEIGHTS['superscripts'] * min(1.0, features.superscripts / 2)

        # Pontuação baseada em padrões booleanos
        # Equação só conta se texto for curto
        if features.has_equation and features.total_chars < 100:
            score += self.WEIGHTS['has_equation']

        if features.has_fraction:
            score += self.WEIGHTS['has_fraction']

        if features.has_power:
            score += self.WEIGHTS['has_power']

        if features.has_function:
            score += self.WEIGHTS['has_function']

        # Número de equação só é relevante se texto for curto
        if features.has_equation_number and features.total_chars < 80:
            score += self.WEIGHTS['has_equation_number']

        # Penalidade para texto muito fragmentado sem estrutura clara
        if self.PATTERNS['fragmented'].search(text) and not features.has_equation:
            score += self.WEIGHTS['fragmented_penalty']

        # Bonus para padrões de atribuição (x = ...) apenas em textos curtos
        if self.PATTERNS['assignment'].search(text) and features.total_chars < 60:
            score += 0.15

        # Penalidade extra para textos com muitas palavras longas (texto normal)
        long_words = len([w for w in text.split() if len(w) > 6 and w.isalpha()])
        if long_words >= 5:
            score -= 0.25

        # Normalizar para 0-1
        return max(0.0, min(1.0, score))

    def classify(self, text: str) -> Tuple[FormulaConfidence, float]:
        """
        Classifica um texto como fórmula ou não.

        Args:
            text: Texto a classificar

        Returns:
            Tupla (nível de confiança, score numérico)
        """
        features = self.extract_features(text)
        score = features.formula_score

        if score >= self.THRESHOLD_HIGH:
            return FormulaConfidence.HIGH, score
        elif score >= self.THRESHOLD_MEDIUM:
            return FormulaConfidence.MEDIUM, score
        elif score >= self.THRESHOLD_LOW:
            return FormulaConfidence.LOW, score
        else:
            return FormulaConfidence.NONE, score

    def is_formula(self, text: str, min_confidence: FormulaConfidence = FormulaConfidence.MEDIUM) -> bool:
        """
        Verifica se o texto é uma fórmula.

        Args:
            text: Texto a verificar
            min_confidence: Confiança mínima para considerar como fórmula

        Returns:
            True se for fórmula com confiança >= min_confidence
        """
        confidence, _ = self.classify(text)
        return confidence.value >= min_confidence.value

    def extract_context(self, text_before: str = "", text_after: str = "") -> FormulaContext:
        """
        Extrai contexto de textos adjacentes para ajudar na reconstrução.

        Args:
            text_before: Texto que aparece antes da fórmula
            text_after: Texto que aparece depois da fórmula

        Returns:
            FormulaContext com informações extraídas
        """
        context = FormulaContext(
            text_before=text_before,
            text_after=text_after
        )

        combined = f"{text_before} {text_after}".lower()

        # Detectar nome da fórmula
        for pattern, name, hint in self._name_patterns:
            if pattern.search(combined):
                context.detected_name = name
                context.context_hint = hint
                break

        # Detectar tipo (definição, equação, lei)
        if re.search(r'\b(defini[çc][ãa]o|definid[ao])\b', combined):
            context.detected_type = 'definição'
        elif re.search(r'\b(lei|law)\b', combined):
            context.detected_type = 'lei'
        elif re.search(r'\b(equa[çc][ãa]o|equation)\b', combined):
            context.detected_type = 'equação'
        elif re.search(r'\b(f[óo]rmula|formula)\b', combined):
            context.detected_type = 'fórmula'

        # Extrair variáveis mencionadas
        for var, (latex_name, meaning) in self.KNOWN_VARIABLES.items():
            if var in combined or latex_name.lower() in combined or meaning.lower() in combined:
                context.related_variables.append(var)

        return context

    def reconstruct_formula(self, text: str, context: Optional[FormulaContext] = None) -> ReconstructedFormula:
        """
        Tenta reconstruir uma fórmula a partir de texto (possivelmente fragmentado).

        Args:
            text: Texto da fórmula
            context: Contexto opcional extraído do texto adjacente

        Returns:
            ReconstructedFormula com o resultado
        """
        confidence, score = self.classify(text)

        # Extrair número da equação se presente
        eq_label = None
        eq_match = self.PATTERNS['equation_number'].search(text)
        if eq_match:
            eq_label = eq_match.group().strip('() ')

        # Se não parece ser fórmula, retornar como está
        if confidence == FormulaConfidence.NONE:
            return ReconstructedFormula(
                original=text,
                latex=text,
                confidence=confidence,
                equation_label=eq_label
            )

        # Tentar usar fórmula conhecida baseada no contexto
        formula_name = None
        context_hint = None
        latex = None

        if context and context.detected_name:
            formula_name = context.detected_name
            context_hint = context.context_hint
            # Verificar se temos uma reconstrução conhecida
            latex = self._try_known_formula(text, context)

        # Se não encontrou fórmula conhecida, tentar reconstruir
        if latex is None:
            latex = self._try_known_formula_by_text(text)

        # Fallback: conversão padrão
        if latex is None:
            latex = self._convert_to_latex(text)

        return ReconstructedFormula(
            original=text,
            latex=latex,
            confidence=confidence,
            equation_label=eq_label,
            formula_name=formula_name,
            context_hint=context_hint
        )

    def _try_known_formula(self, text: str, context: FormulaContext) -> Optional[str]:
        """
        Tenta encontrar uma fórmula conhecida baseada no contexto.

        Args:
            text: Texto da fórmula
            context: Contexto extraído

        Returns:
            LaTeX da fórmula conhecida ou None
        """
        if not context.detected_name:
            return None

        text_lower = text.lower()
        name_lower = context.detected_name.lower()

        # Verificar fórmulas conhecidas
        for pattern, latex in self.KNOWN_FORMULAS.items():
            if pattern in text_lower or pattern in name_lower:
                return latex

        # Se temos um hint de contexto, usar como fallback
        if context.context_hint:
            return context.context_hint

        return None

    def _try_known_formula_by_text(self, text: str) -> Optional[str]:
        """
        Tenta identificar fórmula conhecida apenas pelo texto.

        Args:
            text: Texto da fórmula

        Returns:
            LaTeX da fórmula conhecida ou None
        """
        text_lower = text.lower()
        text_normalized = re.sub(r'\s+', ' ', text_lower).strip()

        # Verificar padrões conhecidos
        for pattern, latex in self.KNOWN_FORMULAS.items():
            if pattern in text_normalized:
                return latex

        # Padrões específicos de fórmulas fragmentadas comuns
        # Massa específica: "ρ = m/V" ou fragmentos como "volume massa"
        if 'massa' in text_lower and 'volume' in text_lower:
            if 'peso' in text_lower:
                return r'\gamma = \frac{W}{V}'
            return r'\rho = \frac{m}{V}'

        # Pressão: "P = F/A"
        if ('pressão' in text_lower or 'pressao' in text_lower) and ('força' in text_lower or 'forca' in text_lower or 'área' in text_lower or 'area' in text_lower):
            return r'P = \frac{F}{A}'

        # Lei de Stevin
        if 'stevin' in text_lower or ('pressão' in text_lower and 'altura' in text_lower and 'peso' in text_lower):
            return r'P = P_0 + \rho g h'

        # Equação dos gases
        if 'pv' in text_lower and ('nrt' in text_lower or 'mrt' in text_lower or 'gas' in text_lower):
            return r'PV = nRT'

        return None

    def reconstruct_with_context(
        self,
        text: str,
        text_before: str = "",
        text_after: str = ""
    ) -> ReconstructedFormula:
        """
        Reconstrói uma fórmula usando o contexto imediato.

        Este é o método principal para usar quando você tem acesso
        ao texto que aparece antes e depois da fórmula.

        Args:
            text: Texto da fórmula (possivelmente fragmentado)
            text_before: Texto que aparece antes da fórmula
            text_after: Texto que aparece depois da fórmula

        Returns:
            ReconstructedFormula com o resultado
        """
        # Extrair contexto
        context = self.extract_context(text_before, text_after)

        # Reconstruir usando contexto
        return self.reconstruct_formula(text, context)

    def _convert_to_latex(self, text: str) -> str:
        """
        Converte texto para LaTeX.

        Args:
            text: Texto a converter

        Returns:
            Texto em formato LaTeX
        """
        result = text

        # Remover número de equação (será adicionado separadamente)
        result = self.PATTERNS['equation_number'].sub('', result)

        # Converter letras gregas escritas por extenso
        greek_map = {
            'alpha': '\\alpha', 'beta': '\\beta', 'gamma': '\\gamma',
            'delta': '\\delta', 'epsilon': '\\epsilon', 'zeta': '\\zeta',
            'eta': '\\eta', 'theta': '\\theta', 'iota': '\\iota',
            'kappa': '\\kappa', 'lambda': '\\lambda', 'mu': '\\mu',
            'nu': '\\nu', 'xi': '\\xi', 'pi': '\\pi',
            'rho': '\\rho', 'sigma': '\\sigma', 'tau': '\\tau',
            'upsilon': '\\upsilon', 'phi': '\\phi', 'chi': '\\chi',
            'psi': '\\psi', 'omega': '\\omega',
            # Maiúsculas
            'Gamma': '\\Gamma', 'Delta': '\\Delta', 'Theta': '\\Theta',
            'Lambda': '\\Lambda', 'Xi': '\\Xi', 'Pi': '\\Pi',
            'Sigma': '\\Sigma', 'Phi': '\\Phi', 'Psi': '\\Psi', 'Omega': '\\Omega',
        }

        for name, latex in greek_map.items():
            pattern = re.compile(r'\b' + name + r'\b', re.IGNORECASE)
            result = pattern.sub(lambda m: latex, result)

        # Converter símbolos Unicode para LaTeX
        unicode_map = {
            '∞': '\\infty', '∑': '\\sum', '∏': '\\prod',
            '∫': '\\int', '∂': '\\partial', '∇': '\\nabla',
            '√': '\\sqrt', '±': '\\pm', '∓': '\\mp',
            '×': '\\times', '÷': '\\div',
            '≤': '\\leq', '≥': '\\geq', '≠': '\\neq',
            '≈': '\\approx', '≡': '\\equiv',
            '∈': '\\in', '∉': '\\notin',
            '⊂': '\\subset', '⊃': '\\supset',
            '∪': '\\cup', '∩': '\\cap',
            '→': '\\rightarrow', '←': '\\leftarrow',
            '↔': '\\leftrightarrow',
            '⇒': '\\Rightarrow', '⇐': '\\Leftarrow',
            'α': '\\alpha', 'β': '\\beta', 'γ': '\\gamma',
            'δ': '\\delta', 'ε': '\\epsilon', 'ζ': '\\zeta',
            'η': '\\eta', 'θ': '\\theta', 'ι': '\\iota',
            'κ': '\\kappa', 'λ': '\\lambda', 'μ': '\\mu',
            'ν': '\\nu', 'ξ': '\\xi', 'π': '\\pi',
            'ρ': '\\rho', 'σ': '\\sigma', 'τ': '\\tau',
            'υ': '\\upsilon', 'φ': '\\phi', 'χ': '\\chi',
            'ψ': '\\psi', 'ω': '\\omega',
            'Γ': '\\Gamma', 'Δ': '\\Delta', 'Θ': '\\Theta',
            'Λ': '\\Lambda', 'Ξ': '\\Xi', 'Π': '\\Pi',
            'Σ': '\\Sigma', 'Φ': '\\Phi', 'Ψ': '\\Psi', 'Ω': '\\Omega',
        }

        for symbol, latex_str in unicode_map.items():
            result = result.replace(symbol, latex_str)

        # Converter subscritos Unicode
        subscript_map = {
            '₀': '_0', '₁': '_1', '₂': '_2', '₃': '_3', '₄': '_4',
            '₅': '_5', '₆': '_6', '₇': '_7', '₈': '_8', '₉': '_9',
        }
        for sub, latex in subscript_map.items():
            result = result.replace(sub, latex)

        # Converter superscritos Unicode
        superscript_map = {
            '⁰': '^0', '¹': '^1', '²': '^2', '³': '^3', '⁴': '^4',
            '⁵': '^5', '⁶': '^6', '⁷': '^7', '⁸': '^8', '⁹': '^9',
        }
        for sup, latex in superscript_map.items():
            result = result.replace(sup, latex)

        # Converter funções matemáticas
        func_map = {
            'sen': '\\sin', 'cos': '\\cos', 'tan': '\\tan', 'tg': '\\tan',
            'log': '\\log', 'ln': '\\ln', 'exp': '\\exp',
            'lim': '\\lim', 'max': '\\max', 'min': '\\min'
        }
        for func, latex_func in func_map.items():
            pattern = re.compile(r'\b' + func + r'\b', re.IGNORECASE)
            result = pattern.sub(lambda m, lf=latex_func: lf, result)

        # Converter frações simples a/b -> \frac{a}{b}
        result = re.sub(r'(\w+)\s*/\s*(\w+)', r'\\frac{\1}{\2}', result)

        # Converter potências x^2 -> x^{2}
        result = re.sub(r'\^(\d+)', r'^{\1}', result)

        # Converter subscritos x_2 -> x_{2}
        result = re.sub(r'_(\d+)', r'_{\1}', result)

        # Limpar backslashes duplicados que podem ter sido criados
        result = re.sub(r'\\\\+', r'\\', result)

        # Limpar espaços excessivos
        result = re.sub(r'\s+', ' ', result).strip()

        return result

    def process_text_block(self, text: str, context_before: str = "", context_after: str = "") -> str:
        """
        Processa um bloco de texto, identificando e formatando fórmulas.

        Args:
            text: Bloco de texto a processar
            context_before: Texto que aparece antes (para contexto)
            context_after: Texto que aparece depois (para contexto)

        Returns:
            Texto com fórmulas formatadas em LaTeX
        """
        if not text:
            return ""

        # Textos muito longos não são fórmulas - retornar como estão
        if len(text) > 150:
            return text

        confidence, score = self.classify(text)

        # Se não é fórmula ou baixa confiança, retornar como está
        if confidence == FormulaConfidence.NONE or confidence == FormulaConfidence.LOW:
            return text

        # Usar contexto se disponível
        if context_before or context_after:
            formula = self.reconstruct_with_context(text, context_before, context_after)
        else:
            formula = self.reconstruct_formula(text)

        # Se é fórmula com alta confiança E texto curto
        if confidence == FormulaConfidence.HIGH and len(text) < 80:
            result = f"$${formula.latex}$$"
            # Adicionar nome da fórmula se detectado
            if formula.formula_name:
                result += f" *({formula.formula_name})*"
            elif formula.equation_label:
                result += f" *({formula.equation_label})*"
            return result

        # Se é fórmula com média confiança E texto curto
        if confidence == FormulaConfidence.MEDIUM and len(text) < 60:
            return f"${formula.latex}$"

        # Caso contrário, retornar texto original
        return text

    def describe_formula(self, text: str, context_before: str = "", context_after: str = "") -> str:
        """
        Gera uma descrição legível da fórmula baseada no contexto.

        Útil para casos onde a fórmula está muito fragmentada mas
        o contexto indica do que se trata.

        Args:
            text: Texto da fórmula
            context_before: Texto anterior
            context_after: Texto posterior

        Returns:
            Descrição da fórmula ou texto original se não identificada
        """
        context = self.extract_context(context_before, context_after)

        if context.detected_name:
            description = f"*{context.detected_name}*"
            if context.context_hint:
                description += f": ${context.context_hint}$"
            return description

        # Tentar identificar pelo texto
        formula = self.reconstruct_formula(text, context)
        if formula.formula_name:
            return f"*{formula.formula_name}*: ${formula.latex}$"

        # Fallback
        return text

    def extract_readable_parts(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Extrai partes legíveis de um texto que pode conter fórmula fragmentada.

        Útil para textos muito fragmentados onde a fórmula não pode ser reconstruída.

        Args:
            text: Texto a processar

        Returns:
            Tupla (texto_legível, número_equação ou None)
        """
        # Extrair número da equação
        eq_label = None
        eq_match = self.PATTERNS['equation_number'].search(text)
        if eq_match:
            eq_label = eq_match.group().strip('() ')

        # Separar palavras legíveis de fragmentos de fórmula
        words = text.split()
        readable = []

        for word in words:
            word_clean = word.strip('.,;:()[]{}')

            # Palavra com 4+ letras é provavelmente texto normal
            if len(word_clean) >= 4 and word_clean.isalpha():
                # Ignorar algumas palavras que são parte de fórmulas
                if word_clean.lower() not in {'sendo', 'onde', 'temos'}:
                    readable.append(word)

            # Palavras conectoras importantes
            elif word_clean.lower() in {'é', 'são', 'ou', 'e', 'como', 'para', 'que'}:
                readable.append(word)

            # Números significativos (não variáveis)
            elif re.match(r'^\d{2,}[.,]?\d*$', word_clean):
                readable.append(word)

        readable_text = ' '.join(readable).strip()

        return readable_text, eq_label

    def get_cache_stats(self) -> Dict[str, int]:
        """Retorna estatísticas do cache."""
        return {
            'cache_size': len(self._cache),
            'cache_max_size': self._cache_max_size,
        }

    def clear_cache(self):
        """Limpa o cache."""
        self._cache.clear()


# Instância global para uso conveniente
_default_ai: Optional[LightFormulaAI] = None


def get_formula_ai() -> LightFormulaAI:
    """Retorna a instância global da IA de fórmulas."""
    global _default_ai
    if _default_ai is None:
        _default_ai = LightFormulaAI()
    return _default_ai


def classify_formula(text: str) -> Tuple[FormulaConfidence, float]:
    """
    Classifica um texto como fórmula ou não.

    Args:
        text: Texto a classificar

    Returns:
        Tupla (nível de confiança, score numérico)
    """
    return get_formula_ai().classify(text)


def is_formula(text: str, min_confidence: FormulaConfidence = FormulaConfidence.MEDIUM) -> bool:
    """
    Verifica se o texto é uma fórmula.

    Args:
        text: Texto a verificar
        min_confidence: Confiança mínima

    Returns:
        True se for fórmula
    """
    return get_formula_ai().is_formula(text, min_confidence)


def process_formula(text: str) -> str:
    """
    Processa texto, formatando fórmulas detectadas.

    Args:
        text: Texto a processar

    Returns:
        Texto com fórmulas formatadas
    """
    return get_formula_ai().process_text_block(text)


def reconstruct_formula(text: str) -> ReconstructedFormula:
    """
    Reconstrói uma fórmula a partir de texto.

    Args:
        text: Texto da fórmula

    Returns:
        Fórmula reconstruída
    """
    return get_formula_ai().reconstruct_formula(text)
