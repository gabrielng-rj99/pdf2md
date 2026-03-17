"""
Módulo avançado de reconstrução de fórmulas fragmentadas.

Este módulo implementa estratégias avançadas para reconstruir fórmulas matemáticas
que foram fragmentadas durante a extração de texto do PDF.

Estratégias implementadas:
1. Agrupamento heurístico de linhas e blocos por proximidade
2. Reconstrução por padrão de símbolos
3. Detecção de continuação de fórmulas multilinha
4. Pós-processamento com regex e normalização

O módulo pode ser habilitado/desabilitado via configuração.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURAÇÃO - Habilitar/Desabilitar módulo
# ============================================================================
# Defina como False para desabilitar completamente este módulo
FORMULA_RECONSTRUCTION_ENABLED = True


class FragmentType(Enum):
    """Tipos de fragmentos de fórmula detectados."""
    OPERATOR_START = "operator_start"      # Começa com operador (+, -, =, etc)
    OPERATOR_END = "operator_end"          # Termina com operador
    SUBSCRIPT = "subscript"                # Subscrito isolado
    SUPERSCRIPT = "superscript"            # Superscrito isolado
    FRACTION_NUM = "fraction_numerator"    # Numerador de fração
    FRACTION_DEN = "fraction_denominator"  # Denominador de fração
    VARIABLE = "variable"                  # Variável isolada
    CONTINUATION = "continuation"          # Continuação de expressão
    COMPLETE = "complete"                  # Expressão completa
    UNKNOWN = "unknown"


@dataclass
class FormulaFragment:
    """Representa um fragmento de fórmula."""
    text: str
    fragment_type: FragmentType
    line_number: int = 0
    y_position: float = 0.0  # Posição vertical (para agrupamento)
    x_position: float = 0.0  # Posição horizontal
    confidence: float = 0.0

    def __post_init__(self):
        self.text = self.text.strip()


@dataclass
class ReconstructedExpression:
    """Expressão matemática reconstruída."""
    original_fragments: List[str]
    reconstructed: str
    latex: str
    confidence: float
    method: str  # Método usado para reconstrução


class FormulaReconstructor:
    """
    Reconstrói fórmulas matemáticas fragmentadas.

    Usa múltiplas estratégias para identificar e juntar fragmentos
    que pertencem à mesma expressão matemática.
    """

    # Operadores que indicam continuação
    CONTINUATION_OPERATORS: Set[str] = {'+', '-', '×', '÷', '·', '=', '<', '>', '≤', '≥', '≠', '≈'}

    # Operadores no início que indicam fragmento
    START_OPERATORS: Set[str] = {'+', '-', '×', '÷', '·', '='}

    # Símbolos que indicam subscrito/superscrito
    SUBSCRIPT_CHARS: Set[str] = set('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₔₕₖₗₘₙₚₛₜ')
    SUPERSCRIPT_CHARS: Set[str] = set('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ')

    # Padrões regex compilados
    PATTERNS = {
        # Fragmentos típicos
        'isolated_operator': re.compile(r'^[\+\-\×\÷\·\=]$'),
        'operator_start': re.compile(r'^[\+\-\×\÷\·\=]\s*\S'),
        'operator_end': re.compile(r'\S\s*[\+\-\×\÷\·\=]$'),
        'fraction_bar': re.compile(r'^[-─—_]+$'),
        'isolated_variable': re.compile(r'^[A-Za-zα-ωΑ-Ω]$'),
        'subscript_only': re.compile(r'^[₀-₉ₐ-ₜ]+$'),
        'superscript_only': re.compile(r'^[⁰¹²³⁴⁵⁶⁷⁸⁹ⁿⁱ⁺⁻⁼⁽⁾]+$'),

        # Padrões de equação
        'equation_part': re.compile(r'[A-Za-zα-ωΑ-Ω]\s*[=<>≤≥≠≈]'),
        'function_call': re.compile(r'\b(sen|cos|tan|log|ln|exp|lim|max|min)\s*\(?'),

        # Limpeza
        'multiple_spaces': re.compile(r'\s{2,}'),
        'space_around_operator': re.compile(r'\s*([\+\-\×\÷\·\=])\s*'),
    }

    # Threshold de proximidade vertical (em pontos) para agrupar linhas
    VERTICAL_PROXIMITY_THRESHOLD = 15.0

    # Threshold de confiança mínima para aceitar reconstrução
    MIN_CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, enabled: bool = FORMULA_RECONSTRUCTION_ENABLED):
        """
        Inicializa o reconstrutor.

        Args:
            enabled: Se False, o módulo retorna os textos sem modificação
        """
        self.enabled = enabled
        self._stats = {
            'fragments_processed': 0,
            'reconstructions_made': 0,
            'time_spent_ms': 0
        }

    def is_enabled(self) -> bool:
        """Retorna se o módulo está habilitado."""
        return self.enabled

    def classify_fragment(self, text: str) -> FragmentType:
        """
        Classifica o tipo de fragmento de fórmula.

        Args:
            text: Texto do fragmento

        Returns:
            Tipo do fragmento
        """
        text = text.strip()

        if not text:
            return FragmentType.UNKNOWN

        # Operador isolado
        if self.PATTERNS['isolated_operator'].match(text):
            return FragmentType.OPERATOR_START

        # Começa com operador
        if self.PATTERNS['operator_start'].match(text):
            return FragmentType.OPERATOR_START

        # Termina com operador
        if self.PATTERNS['operator_end'].search(text):
            return FragmentType.OPERATOR_END

        # Barra de fração
        if self.PATTERNS['fraction_bar'].match(text):
            return FragmentType.FRACTION_NUM  # Indica que há fração

        # Variável isolada
        if self.PATTERNS['isolated_variable'].match(text):
            return FragmentType.VARIABLE

        # Apenas subscritos
        if self.PATTERNS['subscript_only'].match(text):
            return FragmentType.SUBSCRIPT

        # Apenas superscritos
        if self.PATTERNS['superscript_only'].match(text):
            return FragmentType.SUPERSCRIPT

        # Verificar se parece uma expressão completa
        if '=' in text and len(text) > 3:
            return FragmentType.COMPLETE

        return FragmentType.CONTINUATION

    def should_merge(self, frag1: FormulaFragment, frag2: FormulaFragment) -> Tuple[bool, float]:
        """
        Determina se dois fragmentos devem ser unidos.

        Args:
            frag1: Primeiro fragmento
            frag2: Segundo fragmento

        Returns:
            Tupla (deve_unir, confiança)
        """
        # Verificar proximidade vertical
        vertical_dist = abs(frag2.y_position - frag1.y_position)

        # Se estão muito distantes verticalmente, não unir
        if vertical_dist > self.VERTICAL_PROXIMITY_THRESHOLD:
            return False, 0.0

        # Regras de merge baseadas em tipos
        t1, t2 = frag1.fragment_type, frag2.fragment_type

        # Operador no final + qualquer coisa = merge
        if t1 == FragmentType.OPERATOR_END:
            return True, 0.9

        # Qualquer coisa + operador no início = merge
        if t2 == FragmentType.OPERATOR_START:
            return True, 0.9

        # Variável + subscrito/superscrito = merge
        if t1 == FragmentType.VARIABLE and t2 in (FragmentType.SUBSCRIPT, FragmentType.SUPERSCRIPT):
            return True, 0.95

        # Continuação + continuação na mesma linha = merge
        if t1 == FragmentType.CONTINUATION and t2 == FragmentType.CONTINUATION:
            if vertical_dist < 5.0:  # Muito próximos verticalmente
                return True, 0.7

        # Numerador + barra + denominador (detectar fração)
        # Este caso é mais complexo e requer análise de 3 elementos

        return False, 0.0

    def merge_fragments(self, fragments: List[FormulaFragment]) -> str:
        """
        Une uma lista de fragmentos em uma única expressão.

        Args:
            fragments: Lista de fragmentos ordenados

        Returns:
            Texto unido
        """
        if not fragments:
            return ""

        if len(fragments) == 1:
            return fragments[0].text

        result_parts = []

        for i, frag in enumerate(fragments):
            text = frag.text

            # Primeiro fragmento
            if i == 0:
                result_parts.append(text)
                continue

            prev_frag = fragments[i - 1]

            # Decidir se adiciona espaço ou não
            if frag.fragment_type == FragmentType.SUBSCRIPT:
                # Subscrito cola direto
                result_parts.append(text)
            elif frag.fragment_type == FragmentType.SUPERSCRIPT:
                # Superscrito cola direto
                result_parts.append(text)
            elif prev_frag.fragment_type == FragmentType.OPERATOR_END:
                # Após operador, adiciona espaço
                result_parts.append(' ' + text)
            elif frag.fragment_type == FragmentType.OPERATOR_START:
                # Antes de operador, adiciona espaço
                result_parts.append(' ' + text)
            else:
                # Caso geral: adiciona espaço
                result_parts.append(' ' + text)

        return ''.join(result_parts)

    def reconstruct_line_group(self, lines: List[str],
                                y_positions: Optional[List[float]] = None) -> ReconstructedExpression:
        """
        Reconstrói uma fórmula a partir de um grupo de linhas.

        Args:
            lines: Lista de linhas de texto
            y_positions: Posições Y opcionais para cada linha

        Returns:
            Expressão reconstruída
        """
        if not self.enabled:
            return ReconstructedExpression(
                original_fragments=lines,
                reconstructed=' '.join(lines),
                latex=' '.join(lines),
                confidence=1.0,
                method='disabled'
            )

        if not lines:
            return ReconstructedExpression(
                original_fragments=[],
                reconstructed='',
                latex='',
                confidence=0.0,
                method='empty'
            )

        self._stats['fragments_processed'] += len(lines)

        # Criar fragmentos
        fragments = []
        for i, line in enumerate(lines):
            y_pos = y_positions[i] if y_positions and i < len(y_positions) else float(i * 10)
            frag_type = self.classify_fragment(line)
            fragments.append(FormulaFragment(
                text=line,
                fragment_type=frag_type,
                line_number=i,
                y_position=y_pos
            ))

        # Se só tem um fragmento completo, retornar
        if len(fragments) == 1 and fragments[0].fragment_type == FragmentType.COMPLETE:
            return ReconstructedExpression(
                original_fragments=lines,
                reconstructed=fragments[0].text,
                latex=self._to_latex(fragments[0].text),
                confidence=0.95,
                method='single_complete'
            )

        # Agrupar fragmentos que devem ser unidos
        merged_groups = self._group_fragments(fragments)

        # Unir cada grupo
        reconstructed_parts = []
        total_confidence = 0.0

        for group in merged_groups:
            merged = self.merge_fragments(group)
            reconstructed_parts.append(merged)
            # Calcular confiança média do grupo
            if len(group) > 1:
                total_confidence += 0.8  # Confiança de merge
                self._stats['reconstructions_made'] += 1
            else:
                total_confidence += 0.9  # Fragmento único

        final_text = ' '.join(reconstructed_parts)
        final_text = self._normalize_expression(final_text)
        avg_confidence = total_confidence / len(merged_groups) if merged_groups else 0.0

        return ReconstructedExpression(
            original_fragments=lines,
            reconstructed=final_text,
            latex=self._to_latex(final_text),
            confidence=avg_confidence,
            method='heuristic_grouping'
        )

    def _group_fragments(self, fragments: List[FormulaFragment]) -> List[List[FormulaFragment]]:
        """
        Agrupa fragmentos que devem ser unidos.

        Args:
            fragments: Lista de fragmentos

        Returns:
            Lista de grupos de fragmentos
        """
        if not fragments:
            return []

        groups = []
        current_group = [fragments[0]]

        for i in range(1, len(fragments)):
            should_merge, confidence = self.should_merge(current_group[-1], fragments[i])

            if should_merge and confidence >= self.MIN_CONFIDENCE_THRESHOLD:
                current_group.append(fragments[i])
            else:
                groups.append(current_group)
                current_group = [fragments[i]]

        # Adicionar último grupo
        if current_group:
            groups.append(current_group)

        return groups

    def _normalize_expression(self, text: str) -> str:
        """
        Normaliza uma expressão matemática.

        Args:
            text: Texto a normalizar

        Returns:
            Texto normalizado
        """
        # Remover espaços múltiplos
        text = self.PATTERNS['multiple_spaces'].sub(' ', text)

        # Normalizar espaços ao redor de operadores
        text = self.PATTERNS['space_around_operator'].sub(r' \1 ', text)

        # Remover espaços no início e fim
        text = text.strip()

        # Normalizar espaços duplos criados
        text = self.PATTERNS['multiple_spaces'].sub(' ', text)

        return text

    def _to_latex(self, text: str) -> str:
        """
        Converte texto para LaTeX básico.

        Args:
            text: Texto a converter

        Returns:
            Texto em formato LaTeX
        """
        latex = text

        # Mapeamento de caracteres Unicode para LaTeX
        unicode_to_latex = {
            # Letras gregas minúsculas
            'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
            'ε': r'\epsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
            'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu',
            'ν': r'\nu', 'ξ': r'\xi', 'π': r'\pi', 'ρ': r'\rho',
            'σ': r'\sigma', 'τ': r'\tau', 'υ': r'\upsilon', 'φ': r'\phi',
            'χ': r'\chi', 'ψ': r'\psi', 'ω': r'\omega',

            # Letras gregas maiúsculas
            'Γ': r'\Gamma', 'Δ': r'\Delta', 'Θ': r'\Theta', 'Λ': r'\Lambda',
            'Ξ': r'\Xi', 'Π': r'\Pi', 'Σ': r'\Sigma', 'Φ': r'\Phi',
            'Ψ': r'\Psi', 'Ω': r'\Omega',

            # Símbolos matemáticos
            '∞': r'\infty', '∑': r'\sum', '∏': r'\prod', '∫': r'\int',
            '∂': r'\partial', '∇': r'\nabla', '√': r'\sqrt',
            '±': r'\pm', '∓': r'\mp', '×': r'\times', '÷': r'\div',
            '·': r'\cdot', '≤': r'\leq', '≥': r'\geq', '≠': r'\neq',
            '≈': r'\approx', '≡': r'\equiv', '∝': r'\propto',
            '∈': r'\in', '∉': r'\notin', '⊂': r'\subset', '⊃': r'\supset',
            '∪': r'\cup', '∩': r'\cap', '∧': r'\land', '∨': r'\lor',
            '¬': r'\neg', '→': r'\rightarrow', '←': r'\leftarrow',
            '↔': r'\leftrightarrow', '⇒': r'\Rightarrow', '⇐': r'\Leftarrow',
            '∀': r'\forall', '∃': r'\exists', '∅': r'\emptyset',

            # Subscritos
            '₀': '_0', '₁': '_1', '₂': '_2', '₃': '_3', '₄': '_4',
            '₅': '_5', '₆': '_6', '₇': '_7', '₈': '_8', '₉': '_9',

            # Superscritos
            '⁰': '^0', '¹': '^1', '²': '^2', '³': '^3', '⁴': '^4',
            '⁵': '^5', '⁶': '^6', '⁷': '^7', '⁸': '^8', '⁹': '^9',
            'ⁿ': '^n', 'ⁱ': '^i',
        }

        for char, latex_cmd in unicode_to_latex.items():
            latex = latex.replace(char, latex_cmd)

        return latex

    def reconstruct_text_block(self, text: str) -> str:
        """
        Reconstrói fórmulas em um bloco de texto.

        Esta é a função principal para uso no pipeline.
        Analisa o texto, identifica possíveis fórmulas fragmentadas,
        e tenta reconstruí-las.

        Args:
            text: Bloco de texto a processar

        Returns:
            Texto com fórmulas reconstruídas
        """
        if not self.enabled:
            return text

        if not text or not text.strip():
            return text

        # Dividir em linhas
        lines = text.split('\n')

        # Identificar grupos de linhas que parecem ser fórmulas
        result_lines = []
        formula_buffer = []

        for line in lines:
            line_stripped = line.strip()

            if not line_stripped:
                # Linha vazia - processar buffer se houver
                if formula_buffer:
                    reconstructed = self.reconstruct_line_group(formula_buffer)
                    if reconstructed.confidence >= self.MIN_CONFIDENCE_THRESHOLD:
                        result_lines.append(reconstructed.reconstructed)
                    else:
                        result_lines.extend(formula_buffer)
                    formula_buffer = []
                result_lines.append(line)
                continue

            # Verificar se a linha parece ser fragmento de fórmula
            frag_type = self.classify_fragment(line_stripped)

            if frag_type in (FragmentType.OPERATOR_START, FragmentType.OPERATOR_END,
                            FragmentType.SUBSCRIPT, FragmentType.SUPERSCRIPT,
                            FragmentType.VARIABLE):
                # É um fragmento - adicionar ao buffer
                formula_buffer.append(line_stripped)
            elif formula_buffer:
                # Tinha buffer - verificar se continua
                if frag_type == FragmentType.CONTINUATION:
                    formula_buffer.append(line_stripped)
                else:
                    # Processar buffer anterior
                    reconstructed = self.reconstruct_line_group(formula_buffer)
                    if reconstructed.confidence >= self.MIN_CONFIDENCE_THRESHOLD:
                        result_lines.append(reconstructed.reconstructed)
                    else:
                        result_lines.extend(formula_buffer)
                    formula_buffer = []
                    result_lines.append(line)
            else:
                result_lines.append(line)

        # Processar buffer restante
        if formula_buffer:
            reconstructed = self.reconstruct_line_group(formula_buffer)
            if reconstructed.confidence >= self.MIN_CONFIDENCE_THRESHOLD:
                result_lines.append(reconstructed.reconstructed)
            else:
                result_lines.extend(formula_buffer)

        return '\n'.join(result_lines)

    def get_stats(self) -> Dict:
        """Retorna estatísticas de processamento."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'fragments_processed': 0,
            'reconstructions_made': 0,
            'time_spent_ms': 0
        }


# ============================================================================
# Instância global e funções de conveniência
# ============================================================================

_reconstructor: Optional[FormulaReconstructor] = None


def get_reconstructor() -> FormulaReconstructor:
    """Retorna a instância global do reconstrutor."""
    global _reconstructor
    if _reconstructor is None:
        _reconstructor = FormulaReconstructor(enabled=FORMULA_RECONSTRUCTION_ENABLED)
    return _reconstructor


def reconstruct_formulas(text: str) -> str:
    """
    Função de conveniência para reconstruir fórmulas em um texto.

    Args:
        text: Texto a processar

    Returns:
        Texto com fórmulas reconstruídas
    """
    return get_reconstructor().reconstruct_text_block(text)


def is_reconstruction_enabled() -> bool:
    """Verifica se a reconstrução está habilitada."""
    return FORMULA_RECONSTRUCTION_ENABLED and get_reconstructor().is_enabled()
