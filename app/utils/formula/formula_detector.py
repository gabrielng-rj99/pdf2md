"""
Módulo de detecção e formatação de fórmulas matemáticas.

Este módulo identifica expressões matemáticas em texto extraído de PDFs
e as converte para formato LaTeX compatível com Markdown (GitHub/Obsidian/MarkText).

Formatos suportados:
- Inline: $expressão$
- Bloco: $$expressão$$

Características:
- Detecção baseada em padrões e heurísticas (sem ML/LLM)
- Leve e rápido
- Preserva contexto do texto original
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set, Dict
from enum import Enum


class FormulaType(Enum):
    """Tipo de fórmula matemática."""
    INLINE = "inline"    # Fórmula no meio do texto
    BLOCK = "block"      # Fórmula em bloco separado


@dataclass
class Formula:
    """Representa uma fórmula detectada."""
    original: str           # Texto original
    latex: str              # Expressão LaTeX formatada
    formula_type: FormulaType
    confidence: float       # 0.0 a 1.0
    start_pos: int = 0      # Posição inicial no texto
    end_pos: int = 0        # Posição final no texto


@dataclass
class FormulaDetectorConfig:
    """Configuração do detector de fórmulas."""
    # Thresholds
    min_confidence: float = 0.5          # Confiança mínima para considerar fórmula
    min_operators: int = 1               # Mínimo de operadores para ser fórmula

    # Comportamento
    detect_fractions: bool = True        # Detectar frações (a/b)
    detect_subscripts: bool = True       # Detectar subscritos (x_1)
    detect_superscripts: bool = True     # Detectar superscritos (x^2)
    detect_greek: bool = True            # Detectar letras gregas
    detect_special_functions: bool = True # Detectar sin, cos, log, etc.
    detect_chemical: bool = True         # Detectar fórmulas químicas
    reconstruct_fragments: bool = True   # Reconstruir fragmentos de fórmulas

    # Formatação
    block_threshold: int = 50            # Caracteres para considerar bloco
    wrap_inline: bool = True             # Envolver inline com $...$
    wrap_block: bool = True              # Envolver bloco com $$...$$

    # Filtros
    max_length: int = 500                # Comprimento máximo de fórmula
    min_length: int = 3                  # Comprimento mínimo


# Padrões de operadores matemáticos
MATH_OPERATORS = {
    '+', '-', '×', '÷', '·', '±', '∓', '=', '≠', '≈', '≡', '≤', '≥',
    '<', '>', '∞', '∑', '∏', '∫', '∂', '∇', '√', '∝', '∈', '∉', '⊂',
    '⊃', '∩', '∪', '∧', '∨', '¬', '→', '←', '↔', '⇒', '⇐', '⇔',
}

# Caracteres matemáticos especiais
MATH_SPECIAL = {
    'α', 'β', 'γ', 'δ', 'ε', 'ζ', 'η', 'θ', 'ι', 'κ', 'λ', 'μ',
    'ν', 'ξ', 'π', 'ρ', 'σ', 'τ', 'υ', 'φ', 'χ', 'ψ', 'ω',
    'Α', 'Β', 'Γ', 'Δ', 'Ε', 'Ζ', 'Η', 'Θ', 'Ι', 'Κ', 'Λ', 'Μ',
    'Ν', 'Ξ', 'Π', 'Ρ', 'Σ', 'Τ', 'Υ', 'Φ', 'Χ', 'Ψ', 'Ω',
    '∀', '∃', '∄', '∅', '∆', '∇', '∈', '∉', '∋', '∌',
}

# Mapeamento de caracteres Unicode para LaTeX
UNICODE_TO_LATEX = {
    # Letras gregas minúsculas
    'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
    'ε': r'\epsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
    'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu',
    'ν': r'\nu', 'ξ': r'\xi', 'π': r'\pi', 'ρ': r'\rho',
    'σ': r'\sigma', 'τ': r'\tau', 'υ': r'\upsilon', 'φ': r'\phi',
    'χ': r'\chi', 'ψ': r'\psi', 'ω': r'\omega',
    # Letras gregas maiúsculas
    'Γ': r'\Gamma', 'Δ': r'\Delta', 'Θ': r'\Theta', 'Λ': r'\Lambda',
    'Ξ': r'\Xi', 'Π': r'\Pi', 'Σ': r'\Sigma', 'Υ': r'\Upsilon',
    'Φ': r'\Phi', 'Ψ': r'\Psi', 'Ω': r'\Omega',
    # Operadores
    '×': r'\times', '÷': r'\div', '·': r'\cdot', '±': r'\pm',
    '∓': r'\mp', '≠': r'\neq', '≈': r'\approx', '≡': r'\equiv',
    '≤': r'\leq', '≥': r'\geq', '∞': r'\infty', '∑': r'\sum',
    '∏': r'\prod', '∫': r'\int', '∂': r'\partial', '∇': r'\nabla',
    '√': r'\sqrt', '∝': r'\propto',
    # Conjuntos
    '∈': r'\in', '∉': r'\notin', '⊂': r'\subset', '⊃': r'\supset',
    '∩': r'\cap', '∪': r'\cup', '∅': r'\emptyset',
    # Lógica
    '∧': r'\land', '∨': r'\lor', '¬': r'\neg',
    '→': r'\rightarrow', '←': r'\leftarrow', '↔': r'\leftrightarrow',
    '⇒': r'\Rightarrow', '⇐': r'\Leftarrow', '⇔': r'\Leftrightarrow',
    # Quantificadores
    '∀': r'\forall', '∃': r'\exists',
}

# Funções matemáticas comuns
MATH_FUNCTIONS = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh',
    'log', 'ln', 'exp', 'lim', 'max', 'min', 'sup', 'inf',
    'det', 'dim', 'ker', 'deg', 'gcd', 'lcm', 'mod',
    'sen', 'tg', 'cotg', 'cossec',  # Português
}

# Elementos químicos comuns (para detecção de fórmulas químicas)
CHEMICAL_ELEMENTS = {
    'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne',
    'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar',
    'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
    'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr',
    'Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
    'In', 'Sn', 'Sb', 'Te', 'I', 'Xe',
    'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy',
    'Ho', 'Er', 'Tm', 'Yb', 'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt',
    'Au', 'Hg', 'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn',
}

# Padrões regex para detecção
PATTERNS = {
    # Frações: a/b, (a+b)/(c+d)
    'fraction': re.compile(
        r'(?<![a-zA-Z])(\([^)]+\)|[a-zA-Z0-9]+)\s*/\s*(\([^)]+\)|[a-zA-Z0-9]+)(?![a-zA-Z])'
    ),
    # Potências: x^2, x^{n+1}
    'power': re.compile(
        r'([a-zA-Z0-9\)]+)\s*\^\s*(\{[^}]+\}|[a-zA-Z0-9]+|\([^)]+\))'
    ),
    # Índices: x_1, x_{i,j}
    'subscript': re.compile(
        r'([a-zA-Z0-9]+)\s*_\s*(\{[^}]+\}|[a-zA-Z0-9]+)'
    ),
    # Raiz quadrada: sqrt(x), √x
    'sqrt': re.compile(
        r'(?:sqrt|√)\s*[\(\{]?([^)\}]+)[\)\}]?'
    ),
    # Funções: sin(x), log_2(x)
    'function': re.compile(
        r'\b(' + '|'.join(MATH_FUNCTIONS) + r')\s*(?:_\s*(\{[^}]+\}|[a-zA-Z0-9]+))?\s*[\(\[]([^\)\]]+)[\)\]]',
        re.IGNORECASE
    ),
    # Integrais: ∫f(x)dx
    'integral': re.compile(
        r'[∫]\s*(?:_\s*(\{[^}]+\}|[a-zA-Z0-9]+))?\s*(?:\^\s*(\{[^}]+\}|[a-zA-Z0-9]+))?\s*([^d]*)\s*d([a-zA-Z])'
    ),
    # Somatórios: Σ, ∑
    'summation': re.compile(
        r'[Σ∑]\s*(?:_\s*(\{[^}]+\}|[a-zA-Z0-9=]+))?\s*(?:\^\s*(\{[^}]+\}|[a-zA-Z0-9]+))?'
    ),
    # Equações simples: a = b, x + y = z
    'equation': re.compile(
        r'([a-zA-Z0-9\s\+\-\*\/\^\(\)]+)\s*=\s*([a-zA-Z0-9\s\+\-\*\/\^\(\)]+)'
    ),
    # Variáveis com índices numéricos: V1, P2, x1
    'variable_numbered': re.compile(
        r'\b([a-zA-Z])(\d+)\b'
    ),
    # Expressões entre parênteses com operadores
    'parenthetical': re.compile(
        r'\(([^)]*[\+\-\*\/\^][^)]*)\)'
    ),
}


class FormulaDetector:
    """
    Detecta e formata fórmulas matemáticas em texto.

    Uso:
        detector = FormulaDetector()
        result = detector.process_text("A área é A = πr²")
        # result: "A área é $A = \\pi r^{2}$"
    """

    def __init__(self, config: Optional[FormulaDetectorConfig] = None):
        """
        Inicializa o detector de fórmulas.

        Args:
            config: Configuração opcional
        """
        self.config = config or FormulaDetectorConfig()
        self._compiled_patterns = PATTERNS.copy()
        self._fragment_buffer: List[str] = []  # Buffer para reconstruir fragmentos

    def detect_formulas(self, text: str) -> List[Formula]:
        """
        Detecta todas as fórmulas em um texto.

        Args:
            text: Texto a analisar

        Returns:
            Lista de fórmulas detectadas
        """
        if not text or len(text) < self.config.min_length:
            return []

        formulas = []

        # Detectar diferentes tipos de expressões
        formulas.extend(self._detect_equations(text))
        formulas.extend(self._detect_fractions(text))
        formulas.extend(self._detect_powers_subscripts(text))
        formulas.extend(self._detect_functions(text))
        formulas.extend(self._detect_special_symbols(text))
        formulas.extend(self._detect_chemical_formulas(text))

        # Remover duplicatas e sobreposições
        formulas = self._remove_overlaps(formulas)

        # Filtrar por confiança
        formulas = [f for f in formulas if f.confidence >= self.config.min_confidence]

        return sorted(formulas, key=lambda f: f.start_pos)

    def _detect_equations(self, text: str) -> List[Formula]:
        """Detecta equações (expressões com =)."""
        formulas = []

        # Padrão para equações mais complexas
        equation_pattern = re.compile(
            r'(?<![a-zA-Z])([a-zA-Zα-ωΑ-Ω][a-zA-Z0-9α-ωΑ-Ω_\^\{\}]*(?:\s*[\+\-\*\/×÷·]\s*[a-zA-Zα-ωΑ-Ω0-9_\^\{\}\(\)]+)*)\s*=\s*([a-zA-Zα-ωΑ-Ω0-9_\^\{\}\(\)\+\-\*\/×÷·\s]+)'
        )

        for match in equation_pattern.finditer(text):
            original = match.group(0).strip()
            if len(original) >= self.config.min_length and len(original) <= self.config.max_length:
                confidence = self._calculate_equation_confidence(original)
                if confidence >= self.config.min_confidence:
                    latex = self._convert_to_latex(original)
                    formula_type = FormulaType.BLOCK if len(original) > self.config.block_threshold else FormulaType.INLINE
                    formulas.append(Formula(
                        original=original,
                        latex=latex,
                        formula_type=formula_type,
                        confidence=confidence,
                        start_pos=match.start(),
                        end_pos=match.end()
                    ))

        return formulas

    def _detect_fractions(self, text: str) -> List[Formula]:
        """Detecta frações."""
        if not self.config.detect_fractions:
            return []

        formulas = []

        for match in PATTERNS['fraction'].finditer(text):
            original = match.group(0)
            numerator = match.group(1)
            denominator = match.group(2)

            # Evitar coisas como "e/ou", "km/h" que não são fórmulas
            if self._is_common_abbreviation(original):
                continue

            latex = f"\\frac{{{self._convert_to_latex(numerator)}}}{{{self._convert_to_latex(denominator)}}}"
            confidence = self._calculate_fraction_confidence(numerator, denominator)

            formulas.append(Formula(
                original=original,
                latex=latex,
                formula_type=FormulaType.INLINE,
                confidence=confidence,
                start_pos=match.start(),
                end_pos=match.end()
            ))

        return formulas

    def _detect_powers_subscripts(self, text: str) -> List[Formula]:
        """Detecta potências e índices."""
        formulas = []

        if self.config.detect_superscripts:
            for match in PATTERNS['power'].finditer(text):
                original = match.group(0)
                base = match.group(1)
                exponent = match.group(2)

                # Limpar chaves se existirem
                if exponent.startswith('{') and exponent.endswith('}'):
                    exp_clean = exponent[1:-1]
                else:
                    exp_clean = exponent

                latex = f"{self._convert_to_latex(base)}^{{{self._convert_to_latex(exp_clean)}}}"
                confidence = 0.8 if len(exp_clean) <= 3 else 0.6

                formulas.append(Formula(
                    original=original,
                    latex=latex,
                    formula_type=FormulaType.INLINE,
                    confidence=confidence,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))

        if self.config.detect_subscripts:
            for match in PATTERNS['subscript'].finditer(text):
                original = match.group(0)
                base = match.group(1)
                subscript = match.group(2)

                # Limpar chaves se existirem
                if subscript.startswith('{') and subscript.endswith('}'):
                    sub_clean = subscript[1:-1]
                else:
                    sub_clean = subscript

                latex = f"{self._convert_to_latex(base)}_{{{self._convert_to_latex(sub_clean)}}}"
                confidence = 0.7

                formulas.append(Formula(
                    original=original,
                    latex=latex,
                    formula_type=FormulaType.INLINE,
                    confidence=confidence,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))

        return formulas

    def _detect_functions(self, text: str) -> List[Formula]:
        """Detecta funções matemáticas."""
        if not self.config.detect_special_functions:
            return []

        formulas = []

        for match in PATTERNS['function'].finditer(text):
            original = match.group(0)
            func_name = match.group(1).lower()
            subscript = match.group(2)
            argument = match.group(3)

            # Construir LaTeX
            latex_func = f"\\{func_name}"
            if subscript:
                sub_clean = subscript.strip('{}')
                latex_func += f"_{{{sub_clean}}}"

            latex = f"{latex_func}({self._convert_to_latex(argument)})"

            formulas.append(Formula(
                original=original,
                latex=latex,
                formula_type=FormulaType.INLINE,
                confidence=0.9,
                start_pos=match.start(),
                end_pos=match.end()
            ))

        return formulas

    def _detect_special_symbols(self, text: str) -> List[Formula]:
        """Detecta símbolos matemáticos especiais isolados ou em contexto."""
        if not self.config.detect_greek:
            return []

        formulas = []

        # Detectar letras gregas em contexto matemático
        greek_pattern = re.compile(
            r'([α-ωΑ-Ω])(?:\s*=\s*([0-9.,]+))?'
        )

        for match in greek_pattern.finditer(text):
            original = match.group(0)
            greek_letter = match.group(1)
            value = match.group(2)

            if greek_letter in UNICODE_TO_LATEX:
                latex = UNICODE_TO_LATEX[greek_letter]
                if value:
                    latex += f" = {value}"

                formulas.append(Formula(
                    original=original,
                    latex=latex,
                    formula_type=FormulaType.INLINE,
                    confidence=0.8,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))

        return formulas

    def _calculate_equation_confidence(self, text: str) -> float:
        """Calcula a confiança de que um texto é uma equação."""
        confidence = 0.0

        # Tem sinal de igual
        if '=' in text:
            confidence += 0.3

        # Tem operadores matemáticos
        operators_found = sum(1 for op in MATH_OPERATORS if op in text)
        confidence += min(0.3, operators_found * 0.1)

        # Tem letras gregas ou símbolos especiais
        special_found = sum(1 for c in text if c in MATH_SPECIAL)
        confidence += min(0.2, special_found * 0.1)

        # Tem padrão de variável (letra única ou letra+número)
        if re.search(r'\b[a-zA-Z](?:\d+|_\d+)?\b', text):
            confidence += 0.1

        # Penalizar se parece texto comum
        words = text.split()
        common_words = {'de', 'da', 'do', 'em', 'para', 'com', 'que', 'the', 'and', 'or', 'is', 'are'}
        common_count = sum(1 for w in words if w.lower() in common_words)
        confidence -= common_count * 0.15

        return max(0.0, min(1.0, confidence))

    def _calculate_fraction_confidence(self, numerator: str, denominator: str) -> float:
        """Calcula a confiança de que algo é uma fração matemática."""
        confidence = 0.5

        # Numerador e denominador são números ou variáveis simples
        if re.match(r'^[\d\w\(\)\+\-]+$', numerator) and re.match(r'^[\d\w\(\)\+\-]+$', denominator):
            confidence += 0.3

        # Denominador é número comum (unidade de medida provável)
        if denominator.isdigit():
            confidence += 0.1

        return min(1.0, confidence)

    def _convert_to_latex(self, text: str) -> str:
        """Converte texto para LaTeX."""
        result = text

        # Substituir símbolos Unicode por comandos LaTeX
        for unicode_char, latex_cmd in UNICODE_TO_LATEX.items():
            result = result.replace(unicode_char, latex_cmd)

        # Substituir multiplicação implícita
        result = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', result)

        # Converter potências com números: x2 -> x^{2}
        result = re.sub(r'([a-zA-Z])(\d+)(?!\})', r'\1^{\2}', result)

        # Limpar espaços extras
        result = re.sub(r'\s+', ' ', result).strip()

        return result

    def _is_common_abbreviation(self, text: str) -> bool:
        """Verifica se o texto é uma abreviação comum (não fórmula)."""
        common = {
            'e/ou', 'km/h', 'm/s', 'kg/m', 'n/a', 'a/c', 'c/c', 's/n',
            'i/o', 'w/o', 'b/w', 'r/w',
        }
        return text.lower() in common

    def _remove_overlaps(self, formulas: List[Formula]) -> List[Formula]:
        """Remove fórmulas sobrepostas, mantendo a de maior confiança."""
        if len(formulas) <= 1:
            return formulas

        # Ordenar por posição
        formulas.sort(key=lambda f: (f.start_pos, -f.confidence))

        result = []
        last_end = -1

        for formula in formulas:
            if formula.start_pos >= last_end:
                result.append(formula)
                last_end = formula.end_pos
            elif formula.confidence > result[-1].confidence:
                # Substituir se nova tem maior confiança
                result[-1] = formula
                last_end = formula.end_pos

        return result

    def process_text(self, text: str) -> str:
        """
        Processa texto e formata fórmulas detectadas.

        Args:
            text: Texto original

        Returns:
            Texto com fórmulas formatadas em LaTeX
        """
        formulas = self.detect_formulas(text)

        if not formulas:
            return text

        # Aplicar substituições de trás para frente para manter posições
        result = text
        for formula in reversed(formulas):
            if formula.formula_type == FormulaType.BLOCK and self.config.wrap_block:
                replacement = f"$${formula.latex}$$"
            elif formula.formula_type == FormulaType.INLINE and self.config.wrap_inline:
                replacement = f"${formula.latex}$"
            else:
                replacement = formula.latex

            result = result[:formula.start_pos] + replacement + result[formula.end_pos:]

        return result

    def is_formula_line(self, text: str) -> bool:
        """
        Verifica se uma linha inteira é uma fórmula.

        Args:
            text: Linha de texto

        Returns:
            True se a linha parece ser uma fórmula completa
        """
        text = text.strip()

        if not text or len(text) < self.config.min_length:
            return False

        # Calcular score
        score = 0

        # Tem operador de igualdade
        if '=' in text:
            score += 2

        # Tem operadores matemáticos
        operators_count = sum(1 for c in text if c in MATH_OPERATORS or c in '+-*/^')
        score += min(3, operators_count)

        # Tem letras gregas
        greek_count = sum(1 for c in text if c in MATH_SPECIAL)
        score += min(2, greek_count)

        # Tem padrões de fração/potência
        if '/' in text or '^' in text or '_' in text:
            score += 1

        # Proporção de caracteres matemáticos vs texto
        math_chars = sum(1 for c in text if c in MATH_OPERATORS or c in MATH_SPECIAL or c.isdigit() or c in '+-*/^=()[]{}')
        total_chars = len(text.replace(' ', ''))
        if total_chars > 0:
            math_ratio = math_chars / total_chars
            if math_ratio > 0.3:
                score += 2

        # Penalizar texto comum
        words = text.split()
        if len(words) > 5:
            score -= 2

        return score >= 4

    def format_formula_block(self, text: str) -> str:
        """
        Formata uma linha que é uma fórmula completa como bloco.

        Args:
            text: Texto da fórmula

        Returns:
            Fórmula formatada como bloco LaTeX
        """
        latex = self._convert_to_latex(text.strip())
        return f"$$\n{latex}\n$$"

    def _detect_chemical_formulas(self, text: str) -> List[Formula]:
        """Detecta fórmulas químicas (H2O, CO2, Ca(OH)2, etc)."""
        if not self.config.detect_chemical:
            return []

        formulas = []

        # Padrão: Elemento químico seguido de números e parênteses
        # Exemplos: H2O, CO2, Ca(OH)2, CH3CH2OH, 2H2O
        chemical_pattern = re.compile(
            r'(\d*)\s*(' + '|'.join(CHEMICAL_ELEMENTS) + r')(\d+)?(?:\(([A-Z][a-z]?)(\d+)?\)(\d+)?)*'
        )

        for match in chemical_pattern.finditer(text):
            original = match.group(0).strip()

            # Validações para evitar falsos positivos
            if len(original) < 2:
                continue

            # Deve ter pelo menos um número ou múltiplos elementos
            if not re.search(r'\d', original):
                # Se não tem número, deve ter múltiplos elementos
                elem_count = sum(1 for e in CHEMICAL_ELEMENTS if e in original)
                if elem_count < 2:
                    continue

            confidence = self._calculate_chemical_confidence(original)

            if confidence >= self.config.min_confidence:
                latex = self._convert_chemical_to_latex(original)
                formula_type = FormulaType.INLINE

                formulas.append(Formula(
                    original=original,
                    latex=latex,
                    formula_type=formula_type,
                    confidence=confidence,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))

        return formulas

    def _calculate_chemical_confidence(self, text: str) -> float:
        """Calcula confiança de que é fórmula química."""
        confidence = 0.0

        # Tem números (subscritos)
        if re.search(r'\d+', text):
            confidence += 0.4

        # Tem parênteses (comum em químicas)
        if '(' in text and ')' in text:
            confidence += 0.2

        # Começa com número (coeficiente estequiométrico)
        if re.match(r'^\d+', text):
            confidence += 0.2

        # Tem elementos reconhecidos
        elem_count = sum(1 for e in CHEMICAL_ELEMENTS if e in text)
        confidence += min(0.3, elem_count * 0.15)

        # Padrão típico: Elemento maiúsculo seguido de minúscula
        if re.search(r'[A-Z][a-z]', text):
            confidence += 0.1

        return min(1.0, confidence)

    def _convert_chemical_to_latex(self, text: str) -> str:
        """Converte fórmula química para LaTeX."""
        result = text

        # Converter números em subscritos
        # H2O -> H_2O, mas preservar estrutura
        result = re.sub(r'([A-Za-z])\(\s*([A-Za-z]+)\s*(\d+)\)', r'\1(_{\2})_{\3}', result)
        result = re.sub(r'([A-Za-z])(\d+)', r'\1_{\2}', result)

        # Coeficiente estequiométrico em frente
        if re.match(r'^\d+\s*[A-Z]', result):
            result = re.sub(r'^(\d+)\s+', r'\1 ', result)

        return result

    def _detect_formula_fragments(self, lines: List[str]) -> List[Tuple[int, str]]:
        """
        Detecta fragmentos de fórmulas e tenta reconstruir.

        Retorna lista de (índice_linha, fórmula_reconstruída)
        """
        if not self.config.reconstruct_fragments or len(lines) < 2:
            return []

        reconstructed = []

        for i in range(len(lines) - 1):
            current = lines[i].strip()
            next_line = lines[i + 1].strip()

            # Verificar se parece fragmento: tem operadores/símbolos mas sem contexto
            if self._is_formula_fragment(current):
                # Tentar combinar com próxima linha
                combined = f"{current} {next_line}"

                # Se combinada parece melhor, marcar para reconstrução
                if self._is_complete_formula(combined):
                    reconstructed.append((i, combined))

        return reconstructed

    def _is_formula_fragment(self, text: str) -> bool:
        """Verifica se o texto é um fragmento de fórmula."""
        text = text.strip()

        if len(text) < 3 or len(text) > 200:
            return False

        # Indicadores de fragmento
        indicators = 0

        # Tem operadores matemáticos
        if any(op in text for op in ['+', '-', '=', '×', '÷', '/', '^', '_']):
            indicators += 1

        # Tem letras gregas ou símbolos especiais
        if any(c in text for c in MATH_SPECIAL):
            indicators += 1

        # Tem muitos números e letras (padrão matemático)
        letter_count = sum(1 for c in text if c.isalpha())
        digit_count = sum(1 for c in text if c.isdigit())
        if letter_count > 0 and digit_count > 0:
            ratio = digit_count / (letter_count + digit_count)
            if 0.2 < ratio < 0.8:
                indicators += 1

        # Começa ou termina com operador/variável
        if text[0] in ['+', '-', '=', '('] or text[-1] in ['+', '-', '=', ')']:
            indicators += 1

        # Não termina com pontuação comum
        if not text.endswith(('.', ',', ';', ':', '!', '?')):
            indicators += 1

        return indicators >= 2

    def _is_complete_formula(self, text: str) -> bool:
        """Verifica se texto combina parece uma fórmula completa."""
        text = text.strip()

        score = 0

        # Tem igualdade
        if '=' in text:
            score += 3

        # Tem operadores balanceados
        if text.count('(') == text.count(')'):
            score += 1

        # Tem estrutura matemática
        if re.search(r'[a-zA-Z]\s*[=+\-*/]\s*[a-zA-Z0-9]', text):
            score += 2

        # Não é muito longo
        if len(text) < 200:
            score += 1

        return score >= 3

    def get_statistics(self) -> dict:
        """Retorna estatísticas do detector (para debug)."""
        return {
            'config': {
                'min_confidence': self.config.min_confidence,
                'block_threshold': self.config.block_threshold,
            },
            'patterns_count': len(self._compiled_patterns),
        }


def detect_and_format_formulas(text: str, config: Optional[FormulaDetectorConfig] = None) -> str:
    """
    Função de conveniência para detectar e formatar fórmulas.

    Args:
        text: Texto a processar
        config: Configuração opcional

    Returns:
        Texto com fórmulas formatadas
    """
    detector = FormulaDetector(config)
    return detector.process_text(text)


def is_math_expression(text: str) -> bool:
    """
    Verifica rapidamente se um texto parece ser expressão matemática.

    Args:
        text: Texto a verificar

    Returns:
        True se parece ser expressão matemática
    """
    if not text or len(text) < 2:
        return False

    # Indicadores fortes
    strong_indicators = 0

    # Tem operadores matemáticos Unicode
    if any(c in text for c in MATH_OPERATORS):
        strong_indicators += 1

    # Tem letras gregas
    if any(c in text for c in MATH_SPECIAL):
        strong_indicators += 1

    # Tem padrão de equação: x = y
    if re.search(r'[a-zA-Z]\s*=\s*[a-zA-Z0-9]', text):
        strong_indicators += 1

    # Tem potência ou índice
    if '^' in text or re.search(r'_\d', text):
        strong_indicators += 1

    # Tem fração
    if re.search(r'\w/\w', text):
        strong_indicators += 1

    return strong_indicators >= 1
