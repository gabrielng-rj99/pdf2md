"""
Módulo de reconstrução avançada de fórmulas matemáticas.

Este módulo detecta e reconstrói fórmulas matemáticas que foram fragmentadas
durante a extração de PDFs. Resolve problemas como:

1. Frações verticais separadas em linhas diferentes (numerador/denominador)
2. Expoentes e índices separados de suas bases
3. Elementos de equações fora de ordem
4. Símbolos matemáticos isolados que deveriam estar conectados

Pipeline de reconstrução:
1. Análise de linhas adjacentes para detectar padrões de fração
2. Detecção de elementos órfãos (símbolos isolados)
3. Reconstrução baseada em contexto espacial
4. Validação de fórmulas reconstruídas
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set, Iterator
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FragmentType(Enum):
    """Tipo de fragmento de fórmula detectado."""
    NUMERATOR = "numerator"           # Numerador de fração
    DENOMINATOR = "denominator"       # Denominador de fração
    FRACTION_LINE = "fraction_line"   # Linha divisória de fração
    EXPONENT = "exponent"             # Expoente separado
    SUBSCRIPT = "subscript"           # Índice separado
    OPERATOR = "operator"             # Operador isolado
    VARIABLE = "variable"             # Variável isolada
    ORPHAN = "orphan"                 # Fragmento órfão genérico


@dataclass
class FormulaFragment:
    """Representa um fragmento de fórmula detectado."""
    text: str
    fragment_type: FragmentType
    line_number: int
    confidence: float
    context: str = ""  # Texto ao redor para contexto


@dataclass
class ReconstructedFormula:
    """Representa uma fórmula reconstruída."""
    original_lines: List[str]        # Linhas originais
    reconstructed: str               # Fórmula reconstruída
    start_line: int                  # Linha inicial
    end_line: int                    # Linha final
    confidence: float                # Confiança da reconstrução
    reconstruction_type: str         # Tipo de reconstrução aplicada


@dataclass
class FormulaReconstructorConfig:
    """Configuração do reconstrutor de fórmulas."""
    # Detecção de frações
    detect_vertical_fractions: bool = True
    max_fraction_gap: int = 2  # Máximo de linhas entre numerador e denominador
    min_fraction_confidence: float = 0.6

    # Detecção de expoentes/índices
    detect_orphan_exponents: bool = True
    detect_orphan_subscripts: bool = True

    # Reconstrução
    reconstruct_equations: bool = True
    merge_adjacent_fragments: bool = True

    # Validação
    validate_reconstructions: bool = True
    min_reconstruction_confidence: float = 0.5

    # Comportamento
    preserve_original_on_failure: bool = True
    verbose: bool = False


# =============================================================================
# CONJUNTOS DE CARACTERES
# =============================================================================

# Caracteres que indicam numerador/denominador
FRACTION_INDICATORS = set('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
FRACTION_INDICATORS.update('αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ')
FRACTION_INDICATORS.update('+-()[]{}')

# Caracteres que podem ser linha divisória de fração
FRACTION_LINES = set('─━—–-_')

# Operadores que indicam continuação de fórmula
CONTINUATION_OPERATORS = set('+-×÷·=≠≈<>≤≥')

# Símbolos que indicam expoente
EXPONENT_CHARS = set('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿⁱ')

# Símbolos que indicam subscrito
SUBSCRIPT_CHARS = set('₀₁₂₃₄₅₆₇₈₉ₐₑₒₓₙ')

# Letras gregas
GREEK_LETTERS = set('αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ')

# Símbolos matemáticos
MATH_SYMBOLS = set('∞∑∫∂√≤≥≠≈∈∉⊂⊃∩∪→←↔⇒⇐⇔±×÷·∝∀∃∇∆')


# =============================================================================
# PADRÕES REGEX
# =============================================================================

# Linha que parece numerador de fração
NUMERATOR_PATTERN = re.compile(
    r'^[\s]*'  # Espaço opcional no início
    r'([a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω\+\-\*\(\)]+)'  # Expressão
    r'[\s]*$'  # Espaço opcional no fim
)

# Linha que parece denominador de fração
DENOMINATOR_PATTERN = re.compile(
    r'^[\s]*'
    r'([a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω\+\-\*\(\)]+)'
    r'[\s]*$'
)

# Linha que é só traço (divisória de fração)
FRACTION_LINE_PATTERN = re.compile(
    r'^[\s]*[─━—–\-_]{2,}[\s]*$'
)

# Expoente isolado (número ou letra pequeno no início da linha)
ORPHAN_EXPONENT_PATTERN = re.compile(
    r'^[\s]*([0-9n²³⁴⁵⁶⁷⁸⁹⁺⁻])[\s]*$'
)

# Subscrito isolado
ORPHAN_SUBSCRIPT_PATTERN = re.compile(
    r'^[\s]*([0-9₀₁₂₃₄₅₆₇₈₉ₐₑₒₓₙ])[\s]*$'
)

# Operador isolado no início/fim de linha
ORPHAN_OPERATOR_PATTERN = re.compile(
    r'^[\s]*([+\-×÷·=])[\s]*$|'  # Operador sozinho na linha
    r'^[\s]*([+\-×÷·=])[\s]+|'   # Operador no início
    r'[\s]+([+\-×÷·=])[\s]*$'    # Operador no fim
)

# Padrão para detectar fração vertical (3 linhas: num, traço, den)
VERTICAL_FRACTION_PATTERN = re.compile(
    r'([a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω\+\-\(\)]+)\n'  # Numerador
    r'[\s]*[─━—–\-_]+[\s]*\n'                              # Linha
    r'([a-zA-Z0-9αβγδεζηθικλμνξοπρστυφχψω\+\-\(\)]+)',    # Denominador
    re.MULTILINE
)

# Padrão para equação fragmentada: variável = \n expressão
FRAGMENTED_EQUATION_PATTERN = re.compile(
    r'([a-zA-Z][a-zA-Z0-9₀-₉]*)\s*=\s*$',  # Variável = no fim da linha
    re.MULTILINE
)

# Padrão para "sendo" fragmentado (definições de variáveis)
DEFINITION_PATTERN = re.compile(
    r'\bsendo\s*$|\bonde\s*$|\bcom\s*$',
    re.IGNORECASE | re.MULTILINE
)


class FormulaReconstructor:
    """
    Reconstrói fórmulas matemáticas fragmentadas.

    Analisa múltiplas linhas para detectar padrões de fragmentação
    e reconstrói as fórmulas completas.
    """

    def __init__(self, config: Optional[FormulaReconstructorConfig] = None):
        """
        Inicializa o reconstrutor.

        Args:
            config: Configuração opcional
        """
        self.config = config or FormulaReconstructorConfig()
        self._stats = {
            'lines_processed': 0,
            'fractions_reconstructed': 0,
            'equations_reconstructed': 0,
            'orphans_merged': 0,
            'total_reconstructions': 0,
        }

    def reconstruct(self, text: str) -> str:
        """
        Reconstrói fórmulas fragmentadas em um texto.

        Args:
            text: Texto completo a processar

        Returns:
            Texto com fórmulas reconstruídas
        """
        if not text:
            return text

        lines = text.split('\n')
        self._stats['lines_processed'] = len(lines)

        # Fase 1: Detectar e reconstruir frações verticais
        if self.config.detect_vertical_fractions:
            lines = self._reconstruct_vertical_fractions(lines)

        # Fase 2: Detectar e reconstruir equações fragmentadas
        if self.config.reconstruct_equations:
            lines = self._reconstruct_fragmented_equations(lines)

        # Fase 3: Mesclar fragmentos órfãos
        if self.config.merge_adjacent_fragments:
            lines = self._merge_orphan_fragments(lines)

        # Fase 4: Reconstruir expoentes/índices órfãos
        if self.config.detect_orphan_exponents:
            lines = self._reconstruct_orphan_exponents(lines)

        if self.config.detect_orphan_subscripts:
            lines = self._reconstruct_orphan_subscripts(lines)

        return '\n'.join(lines)

    def _reconstruct_vertical_fractions(self, lines: List[str]) -> List[str]:
        """
        Reconstrói frações que foram divididas verticalmente.

        Padrão:
            linha 1: numerador
            linha 2: ────── (traço)
            linha 3: denominador

        Resultado:
            numerador/denominador
        """
        if len(lines) < 3:
            return lines

        result = []
        i = 0

        while i < len(lines):
            # Verificar se temos padrão de fração vertical
            if i + 2 < len(lines):
                is_fraction, confidence = self._is_vertical_fraction(
                    lines[i], lines[i+1], lines[i+2]
                )

                if is_fraction and confidence >= self.config.min_fraction_confidence:
                    # Extrair numerador e denominador
                    num = lines[i].strip()
                    den = lines[i+2].strip()

                    # Reconstruir fração
                    fraction = f"({num})/({den})" if '+' in num or '-' in num or '+' in den or '-' in den else f"{num}/{den}"

                    result.append(fraction)
                    self._stats['fractions_reconstructed'] += 1
                    self._stats['total_reconstructions'] += 1

                    if self.config.verbose:
                        logger.debug(f"Fração reconstruída: {num}/{den}")

                    i += 3  # Pular as 3 linhas da fração
                    continue

            result.append(lines[i])
            i += 1

        return result

    def _is_vertical_fraction(
        self,
        line1: str,
        line2: str,
        line3: str
    ) -> Tuple[bool, float]:
        """
        Verifica se 3 linhas formam uma fração vertical.

        Returns:
            Tupla (is_fraction, confidence)
        """
        confidence = 0.0

        # Linha 2 deve ser traço
        if not FRACTION_LINE_PATTERN.match(line2):
            # Verificar se é linha com múltiplos traços
            stripped = line2.strip()
            if not (len(stripped) >= 2 and all(c in FRACTION_LINES for c in stripped)):
                return False, 0.0

        confidence += 0.4

        # Linha 1 deve parecer numerador
        line1_stripped = line1.strip()
        if not line1_stripped:
            return False, 0.0

        if NUMERATOR_PATTERN.match(line1_stripped):
            confidence += 0.3

        # Linha 3 deve parecer denominador
        line3_stripped = line3.strip()
        if not line3_stripped:
            return False, 0.0

        if DENOMINATOR_PATTERN.match(line3_stripped):
            confidence += 0.3

        # Bônus se contém letras/símbolos matemáticos
        if any(c in line1_stripped + line3_stripped for c in GREEK_LETTERS | MATH_SYMBOLS):
            confidence += 0.1

        # Penalidade se linhas são muito longas (provavelmente texto normal)
        if len(line1_stripped) > 30 or len(line3_stripped) > 30:
            confidence -= 0.3

        # Penalidade se contém espaços (palavras, não expressão)
        if ' ' in line1_stripped or ' ' in line3_stripped:
            # Mas não penalizar se é pequeno (pode ser "x + y")
            if len(line1_stripped.split()) > 3 or len(line3_stripped.split()) > 3:
                confidence -= 0.4

        return confidence >= 0.5, max(0.0, min(1.0, confidence))

    def _reconstruct_fragmented_equations(self, lines: List[str]) -> List[str]:
        """
        Reconstrói equações que foram fragmentadas em múltiplas linhas.

        Padrão:
            linha 1: "ρ ="
            linha 2: "m/V"

        Resultado:
            "ρ = m/V"
        """
        if len(lines) < 2:
            return lines

        result = []
        i = 0

        while i < len(lines):
            current = lines[i].strip()

            # Verificar se linha termina com "="
            if current.endswith('=') and i + 1 < len(lines):
                next_line = lines[i+1].strip()

                # Próxima linha tem conteúdo matemático?
                if next_line and self._looks_like_expression(next_line):
                    # Mesclar linhas
                    merged = f"{current} {next_line}"
                    result.append(merged)
                    self._stats['equations_reconstructed'] += 1
                    self._stats['total_reconstructions'] += 1

                    if self.config.verbose:
                        logger.debug(f"Equação reconstruída: {merged}")

                    i += 2
                    continue

            # Verificar padrão "sendo" no fim da linha
            if DEFINITION_PATTERN.search(current) and i + 1 < len(lines):
                next_line = lines[i+1].strip()
                if next_line:
                    # Mesclar com definição
                    merged = f"{current} {next_line}"
                    result.append(merged)
                    i += 2
                    continue

            result.append(lines[i])
            i += 1

        return result

    def _merge_orphan_fragments(self, lines: List[str]) -> List[str]:
        """
        Mescla fragmentos órfãos com suas linhas adjacentes.

        Exemplos:
        - Operador isolado no início da linha
        - Variável única que deveria estar na linha anterior
        """
        if len(lines) < 2:
            return lines

        result = []
        i = 0

        while i < len(lines):
            current = lines[i].strip()

            # Verificar se é fragmento órfão
            if self._is_orphan_fragment(current):
                # Tentar mesclar com linha anterior
                if result and self._can_merge_with_previous(result[-1], current):
                    result[-1] = f"{result[-1]} {current}"
                    self._stats['orphans_merged'] += 1
                    i += 1
                    continue

                # Tentar mesclar com próxima linha
                if i + 1 < len(lines) and self._can_merge_with_next(current, lines[i+1]):
                    merged = f"{current} {lines[i+1].strip()}"
                    result.append(merged)
                    self._stats['orphans_merged'] += 1
                    i += 2
                    continue

            result.append(lines[i])
            i += 1

        return result

    def _is_orphan_fragment(self, text: str) -> bool:
        """Verifica se texto é um fragmento órfão."""
        if not text or len(text) > 10:
            return False

        stripped = text.strip()

        # Operador isolado
        if ORPHAN_OPERATOR_PATTERN.match(stripped):
            return True

        # Expoente isolado
        if ORPHAN_EXPONENT_PATTERN.match(stripped):
            return True

        # Subscrito isolado
        if ORPHAN_SUBSCRIPT_PATTERN.match(stripped):
            return True

        # Variável única (uma letra)
        if len(stripped) == 1 and stripped.isalpha():
            return True

        # Letra grega isolada
        if len(stripped) == 1 and stripped in GREEK_LETTERS:
            return True

        return False

    def _can_merge_with_previous(self, prev_line: str, fragment: str) -> bool:
        """Verifica se fragmento pode ser mesclado com linha anterior."""
        prev_stripped = prev_line.strip()

        if not prev_stripped:
            return False

        # Se linha anterior termina com operador, mesclar
        if prev_stripped[-1] in CONTINUATION_OPERATORS:
            return True

        # Se fragmento começa com operador, mesclar
        if fragment.strip() and fragment.strip()[0] in CONTINUATION_OPERATORS:
            return True

        # Se linha anterior termina com variável/número e fragmento é expoente
        if prev_stripped[-1].isalnum() and fragment.strip() in EXPONENT_CHARS:
            return True

        return False

    def _can_merge_with_next(self, fragment: str, next_line: str) -> bool:
        """Verifica se fragmento pode ser mesclado com próxima linha."""
        next_stripped = next_line.strip()

        if not next_stripped:
            return False

        # Se fragmento é operador e próxima linha tem conteúdo matemático
        if fragment.strip() in CONTINUATION_OPERATORS:
            return self._looks_like_expression(next_stripped)

        return False

    def _reconstruct_orphan_exponents(self, lines: List[str]) -> List[str]:
        """
        Reconstrói expoentes órfãos.

        Padrão:
            linha 1: "x"
            linha 2: "2" (expoente)

        Resultado:
            "x²"
        """
        if len(lines) < 2:
            return lines

        result = []
        i = 0

        while i < len(lines):
            current = lines[i].strip()

            # Verificar se próxima linha é expoente órfão
            if i + 1 < len(lines):
                next_stripped = lines[i+1].strip()

                if ORPHAN_EXPONENT_PATTERN.match(next_stripped):
                    # Verificar se linha atual termina com base válida
                    if current and current[-1].isalnum():
                        # Converter para superscrito se possível
                        exp_map = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
                                   '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
                                   'n': 'ⁿ', '+': '⁺', '-': '⁻'}

                        exp_char = exp_map.get(next_stripped, f'^{next_stripped}')
                        merged = f"{current}{exp_char}"
                        result.append(merged)
                        i += 2
                        continue

            result.append(lines[i])
            i += 1

        return result

    def _reconstruct_orphan_subscripts(self, lines: List[str]) -> List[str]:
        """
        Reconstrói subscritos órfãos.

        Similar a expoentes, mas para índices.
        """
        if len(lines) < 2:
            return lines

        result = []
        i = 0

        while i < len(lines):
            current = lines[i].strip()

            # Verificar se próxima linha é subscrito órfão
            if i + 1 < len(lines):
                next_stripped = lines[i+1].strip()

                if ORPHAN_SUBSCRIPT_PATTERN.match(next_stripped):
                    # Verificar se linha atual termina com base válida
                    if current and current[-1].isalpha():
                        # Converter para subscrito se possível
                        sub_map = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
                                   '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
                                   'n': 'ₙ', 'a': 'ₐ', 'e': 'ₑ', 'o': 'ₒ', 'x': 'ₓ'}

                        sub_char = sub_map.get(next_stripped, f'_{next_stripped}')
                        merged = f"{current}{sub_char}"
                        result.append(merged)
                        i += 2
                        continue

            result.append(lines[i])
            i += 1

        return result

    def _looks_like_expression(self, text: str) -> bool:
        """Verifica se texto parece uma expressão matemática."""
        if not text:
            return False

        # Tem letras gregas ou símbolos matemáticos
        if any(c in text for c in GREEK_LETTERS | MATH_SYMBOLS):
            return True

        # Tem padrão de fração
        if '/' in text and len(text) < 20:
            return True

        # Tem operadores matemáticos
        if any(c in text for c in '+-*/^_='):
            return True

        # É uma variável simples (uma letra)
        if len(text) <= 3 and text[0].isalpha():
            return True

        return False

    def detect_fragments(self, text: str) -> List[FormulaFragment]:
        """
        Detecta fragmentos de fórmula em um texto.

        Args:
            text: Texto a analisar

        Returns:
            Lista de fragmentos detectados
        """
        fragments = []
        lines = text.split('\n')

        for i, line in enumerate(lines):
            stripped = line.strip()

            if not stripped:
                continue

            # Verificar diferentes tipos de fragmentos
            fragment_type = None
            confidence = 0.0

            # Linha de fração
            if FRACTION_LINE_PATTERN.match(stripped):
                fragment_type = FragmentType.FRACTION_LINE
                confidence = 0.9

            # Expoente órfão
            elif ORPHAN_EXPONENT_PATTERN.match(stripped):
                fragment_type = FragmentType.EXPONENT
                confidence = 0.7

            # Subscrito órfão
            elif ORPHAN_SUBSCRIPT_PATTERN.match(stripped):
                fragment_type = FragmentType.SUBSCRIPT
                confidence = 0.7

            # Operador órfão
            elif ORPHAN_OPERATOR_PATTERN.match(stripped):
                fragment_type = FragmentType.OPERATOR
                confidence = 0.8

            # Variável isolada
            elif len(stripped) <= 2 and stripped[0].isalpha():
                fragment_type = FragmentType.VARIABLE
                confidence = 0.5

            if fragment_type:
                fragments.append(FormulaFragment(
                    text=stripped,
                    fragment_type=fragment_type,
                    line_number=i,
                    confidence=confidence,
                    context=self._get_context(lines, i)
                ))

        return fragments

    def _get_context(self, lines: List[str], index: int, window: int = 2) -> str:
        """Obtém contexto ao redor de uma linha."""
        start = max(0, index - window)
        end = min(len(lines), index + window + 1)

        context_lines = lines[start:end]
        return ' | '.join(l.strip() for l in context_lines if l.strip())

    def get_stats(self) -> Dict:
        """Retorna estatísticas de processamento."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'lines_processed': 0,
            'fractions_reconstructed': 0,
            'equations_reconstructed': 0,
            'orphans_merged': 0,
            'total_reconstructions': 0,
        }


def get_formula_reconstructor(
    config: Optional[FormulaReconstructorConfig] = None
) -> FormulaReconstructor:
    """Factory function para obter instância do reconstrutor."""
    return FormulaReconstructor(config)


def reconstruct_formulas(text: str) -> str:
    """
    Função utilitária para reconstruir fórmulas fragmentadas.

    Args:
        text: Texto a processar

    Returns:
        Texto com fórmulas reconstruídas
    """
    reconstructor = FormulaReconstructor()
    return reconstructor.reconstruct(text)


def detect_formula_fragments(text: str) -> List[FormulaFragment]:
    """
    Função utilitária para detectar fragmentos de fórmulas.

    Args:
        text: Texto a analisar

    Returns:
        Lista de fragmentos detectados
    """
    reconstructor = FormulaReconstructor()
    return reconstructor.detect_fragments(text)


def fix_fraction_on_multiple_lines(lines: List[str]) -> List[str]:
    """
    Corrige frações que aparecem em múltiplas linhas.

    Args:
        lines: Lista de linhas

    Returns:
        Lista de linhas com frações corrigidas
    """
    config = FormulaReconstructorConfig(
        detect_vertical_fractions=True,
        reconstruct_equations=False,
        merge_adjacent_fragments=False,
        detect_orphan_exponents=False,
        detect_orphan_subscripts=False,
    )
    reconstructor = FormulaReconstructor(config)

    text = '\n'.join(lines)
    result = reconstructor.reconstruct(text)
    return result.split('\n')


def merge_equation_lines(lines: List[str]) -> List[str]:
    """
    Mescla linhas de equações fragmentadas.

    Args:
        lines: Lista de linhas

    Returns:
        Lista de linhas com equações mescladas
    """
    config = FormulaReconstructorConfig(
        detect_vertical_fractions=False,
        reconstruct_equations=True,
        merge_adjacent_fragments=True,
        detect_orphan_exponents=False,
        detect_orphan_subscripts=False,
    )
    reconstructor = FormulaReconstructor(config)

    text = '\n'.join(lines)
    result = reconstructor.reconstruct(text)
    return result.split('\n')
