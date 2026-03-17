"""
Módulo de fusão de fragmentos de fórmulas matemáticas.

Este módulo implementa a "Regra dos Três Sinais" para fundir fragmentos
de fórmulas que foram quebrados durante a extração de texto do PDF.

Heurísticas implementadas:
1. Ponte Sintática - Detecta operadores pendentes no final/início
2. Balanço de Chaves - Conta aberturas/fechamentos de delimitadores
3. Geometria Vertical - Analisa proximidade vertical entre fragmentos

O objetivo é reconstruir fórmulas como "P1.V1/C1 = P2.V2/C2" que
podem ter sido extraídas como "p1/c1", "p2.v2", "=", "c1", "c2".
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MergeReason(Enum):
    """Razão pela qual dois fragmentos foram fundidos."""
    SYNTACTIC_BRIDGE = "syntactic_bridge"    # Operador pendente
    BRACE_BALANCE = "brace_balance"          # Chaves desbalanceadas
    VERTICAL_PROXIMITY = "vertical_proximity" # Proximidade vertical
    CONTINUATION = "continuation"             # Continuação óbvia
    NONE = "none"                            # Não fundir


@dataclass
class FormulaFragment:
    """Representa um fragmento de fórmula."""
    text: str
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    page_num: int = 0

    @property
    def height(self) -> float:
        """Altura do fragmento."""
        return self.y1 - self.y0

    @property
    def width(self) -> float:
        """Largura do fragmento."""
        return self.x1 - self.x0


@dataclass
class MergedFormula:
    """Representa uma fórmula após fusão de fragmentos."""
    text: str
    original_fragments: List[str]
    merge_reasons: List[MergeReason]
    confidence: float
    bbox: Tuple[float, float, float, float]  # União das bboxes


@dataclass
class FormulaMergerConfig:
    """Configuração do fusionador de fórmulas."""
    # Proximidade vertical máxima para fusão (pixels)
    max_vertical_gap: float = 15.0

    # Tolerância para considerar "mesma linha"
    same_line_tolerance: float = 5.0

    # Modo de fusão
    soft_merge: bool = True  # Adiciona espaço entre fragmentos
    latex_line_break: bool = False  # Adiciona \\\\ entre linhas

    # Limites
    max_fragments_to_merge: int = 20
    min_fragment_length: int = 1


# Operadores que indicam continuação quando no FINAL de um fragmento
END_OPERATORS: Set[str] = {
    '+', '-', '=', '×', '·', '÷', '/',
    '*', '<', '>', '≤', '≥', '≠', '≈',
    '(', '[', '{', '\\left', '\\left(',
    ',', ';', ':', '∈', '⊂', '∧', '∨',
}

# Operadores que indicam continuação quando no INÍCIO de um fragmento
START_OPERATORS: Set[str] = {
    '+', '-', '=', '×', '·', '÷', '/',
    '*', '<', '>', '≤', '≥', '≠', '≈',
    ')', ']', '}', '\\right', '\\right)',
    '^', '_', '!',  # Exponente, subscrito, fatorial
}

# Delimitadores de abertura
OPENING_DELIMITERS: Set[str] = {'(', '[', '{', '\\{', '\\left(', '\\left[', '\\left\\{'}

# Delimitadores de fechamento
CLOSING_DELIMITERS: Set[str] = {')', ']', '}', '\\}', '\\right)', '\\right]', '\\right\\}'}

# Padrões de início de ambiente LaTeX
ENVIRONMENT_START = re.compile(r'\\begin\{[^}]+\}')
ENVIRONMENT_END = re.compile(r'\\end\{[^}]+\}')


class FormulaMerger:
    """
    Funde fragmentos de fórmulas matemáticas usando heurísticas.

    Implementa a "Regra dos Três Sinais":
    1. Ponte Sintática
    2. Balanço de Chaves
    3. Geometria Vertical
    """

    def __init__(self, config: Optional[FormulaMergerConfig] = None):
        """
        Inicializa o fusionador.

        Args:
            config: Configuração opcional
        """
        self.config = config or FormulaMergerConfig()
        self._stats = {
            'fragments_processed': 0,
            'merges_performed': 0,
            'syntactic_merges': 0,
            'brace_merges': 0,
            'proximity_merges': 0,
        }

    def merge_fragments(self, fragments: List[FormulaFragment]) -> List[MergedFormula]:
        """
        Funde uma lista de fragmentos em fórmulas completas.

        Args:
            fragments: Lista de fragmentos a fundir

        Returns:
            Lista de fórmulas fundidas
        """
        if not fragments:
            return []

        self._stats['fragments_processed'] += len(fragments)

        merged = []
        buffer = None
        current_reasons = []
        original_texts = []

        for fragment in fragments:
            if buffer is None:
                buffer = fragment
                original_texts = [fragment.text]
                current_reasons = []
                continue

            # Verificar se deve fundir
            should_merge, reason = self._should_merge(buffer, fragment)

            if should_merge:
                buffer = self._merge_two(buffer, fragment, reason)
                original_texts.append(fragment.text)
                current_reasons.append(reason)
                self._stats['merges_performed'] += 1
                self._update_reason_stats(reason)
            else:
                # Finalizar fórmula atual e começar nova
                merged.append(self._create_merged_formula(
                    buffer, original_texts, current_reasons
                ))
                buffer = fragment
                original_texts = [fragment.text]
                current_reasons = []

        # Adicionar último buffer
        if buffer:
            merged.append(self._create_merged_formula(
                buffer, original_texts, current_reasons
            ))

        return merged

    def _should_merge(
        self,
        frag_a: FormulaFragment,
        frag_b: FormulaFragment
    ) -> Tuple[bool, MergeReason]:
        """
        Determina se dois fragmentos devem ser fundidos.

        Aplica as três heurísticas em ordem de prioridade:
        1. Balanço de Chaves (mais forte)
        2. Ponte Sintática
        3. Geometria Vertical

        Args:
            frag_a: Primeiro fragmento (atual/buffer)
            frag_b: Segundo fragmento (próximo)

        Returns:
            Tupla (should_merge, reason)
        """
        text_a = frag_a.text.strip()
        text_b = frag_b.text.strip()

        if not text_a or not text_b:
            return False, MergeReason.NONE

        # Calcular distância vertical
        vertical_gap = frag_b.y0 - frag_a.y1
        is_close = vertical_gap < self.config.max_vertical_gap

        # 1. HEURÍSTICA DO BALANÇO DE CHAVES (mais forte)
        if self._has_unbalanced_delimiters(text_a):
            if is_close or vertical_gap < self.config.max_vertical_gap * 2:
                return True, MergeReason.BRACE_BALANCE

        # Verificar ambientes LaTeX não fechados
        if self._has_unclosed_environment(text_a):
            return True, MergeReason.BRACE_BALANCE

        # 2. HEURÍSTICA DA PONTE SINTÁTICA
        if self._ends_with_operator(text_a):
            if is_close:
                return True, MergeReason.SYNTACTIC_BRIDGE

        if self._starts_with_continuation(text_b):
            if is_close:
                return True, MergeReason.SYNTACTIC_BRIDGE

        # 3. HEURÍSTICA DA GEOMETRIA VERTICAL
        if is_close:
            # Verificar se estão na "mesma linha" ou próximos
            same_line = abs(frag_a.y0 - frag_b.y0) < self.config.same_line_tolerance
            if same_line:
                return True, MergeReason.VERTICAL_PROXIMITY

        return False, MergeReason.NONE

    def _has_unbalanced_delimiters(self, text: str) -> bool:
        """
        Verifica se o texto tem delimitadores desbalanceados.

        Conta aberturas vs fechamentos de (), [], {}.
        """
        # Contagem simples
        open_count = text.count('(') + text.count('[') + text.count('{')
        close_count = text.count(')') + text.count(']') + text.count('}')

        if open_count != close_count:
            return True

        # Verificar LaTeX delimiters
        left_count = text.count('\\left')
        right_count = text.count('\\right')

        if left_count != right_count:
            return True

        # Verificar ambientes
        begin_count = len(ENVIRONMENT_START.findall(text))
        end_count = len(ENVIRONMENT_END.findall(text))

        if begin_count != end_count:
            return True

        return False

    def _has_unclosed_environment(self, text: str) -> bool:
        """Verifica se há ambiente LaTeX não fechado."""
        begins = ENVIRONMENT_START.findall(text)
        ends = ENVIRONMENT_END.findall(text)

        return len(begins) > len(ends)

    def _ends_with_operator(self, text: str) -> bool:
        """Verifica se o texto termina com operador pendente."""
        text = text.rstrip()
        if not text:
            return False

        # Verificar último caractere
        last_char = text[-1]
        if last_char in END_OPERATORS:
            return True

        # Verificar comandos LaTeX no final
        for op in END_OPERATORS:
            if text.endswith(op):
                return True

        return False

    def _starts_with_continuation(self, text: str) -> bool:
        """
        Verifica se o texto começa com algo que indica continuação.

        Elementos como ^, _, ), ] não podem iniciar uma expressão válida.
        """
        text = text.lstrip()
        if not text:
            return False

        first_char = text[0]

        # Caracteres que nunca iniciam uma expressão
        if first_char in {'^', '_', ')', ']', '}', '!'}:
            return True

        # Operadores binários (exceto + e - que podem ser unários)
        if first_char in {'×', '÷', '·', '*', '/', '=', '≠', '≈', '≤', '≥'}:
            return True

        return False

    def _merge_two(
        self,
        frag_a: FormulaFragment,
        frag_b: FormulaFragment,
        reason: MergeReason
    ) -> FormulaFragment:
        """
        Funde dois fragmentos em um.

        Args:
            frag_a: Primeiro fragmento
            frag_b: Segundo fragmento
            reason: Razão da fusão

        Returns:
            Fragmento fundido
        """
        text_a = frag_a.text.strip()
        text_b = frag_b.text.strip()

        # Determinar separador baseado no tipo de fusão
        if reason == MergeReason.SYNTACTIC_BRIDGE:
            # Fusão suave - adiciona espaço se não termina/começa com operador
            if self._ends_with_operator(text_a):
                separator = " "
            else:
                separator = " "
        elif reason == MergeReason.VERTICAL_PROXIMITY:
            # Verificar se é multilinha
            vertical_gap = frag_b.y0 - frag_a.y1
            if vertical_gap > self.config.same_line_tolerance and self.config.latex_line_break:
                separator = " \\\\ "
            else:
                separator = " "
        else:
            separator = " " if self.config.soft_merge else ""

        merged_text = text_a + separator + text_b

        # Calcular nova bbox (união)
        new_bbox = (
            min(frag_a.x0, frag_b.x0),
            min(frag_a.y0, frag_b.y0),
            max(frag_a.x1, frag_b.x1),
            max(frag_a.y1, frag_b.y1),
        )

        return FormulaFragment(
            text=merged_text,
            x0=new_bbox[0],
            y0=new_bbox[1],
            x1=new_bbox[2],
            y1=new_bbox[3],
            page_num=frag_a.page_num,
        )

    def _create_merged_formula(
        self,
        fragment: FormulaFragment,
        original_texts: List[str],
        reasons: List[MergeReason]
    ) -> MergedFormula:
        """Cria objeto MergedFormula a partir do fragmento fundido."""
        # Calcular confiança baseada nas razões de fusão
        if not reasons:
            confidence = 1.0
        else:
            # Média ponderada das razões
            weights = {
                MergeReason.BRACE_BALANCE: 0.95,
                MergeReason.SYNTACTIC_BRIDGE: 0.85,
                MergeReason.VERTICAL_PROXIMITY: 0.70,
                MergeReason.CONTINUATION: 0.80,
                MergeReason.NONE: 0.50,
            }
            confidence = sum(weights.get(r, 0.5) for r in reasons) / len(reasons)

        return MergedFormula(
            text=fragment.text,
            original_fragments=original_texts,
            merge_reasons=reasons,
            confidence=confidence,
            bbox=(fragment.x0, fragment.y0, fragment.x1, fragment.y1),
        )

    def _update_reason_stats(self, reason: MergeReason):
        """Atualiza estatísticas por razão de fusão."""
        if reason == MergeReason.SYNTACTIC_BRIDGE:
            self._stats['syntactic_merges'] += 1
        elif reason == MergeReason.BRACE_BALANCE:
            self._stats['brace_merges'] += 1
        elif reason == MergeReason.VERTICAL_PROXIMITY:
            self._stats['proximity_merges'] += 1

    def get_stats(self) -> dict:
        """Retorna estatísticas de processamento."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'fragments_processed': 0,
            'merges_performed': 0,
            'syntactic_merges': 0,
            'brace_merges': 0,
            'proximity_merges': 0,
        }


def get_formula_merger(config: Optional[FormulaMergerConfig] = None) -> FormulaMerger:
    """Factory function para obter instância do fusionador."""
    return FormulaMerger(config)


def merge_formula_fragments(
    fragments: List[dict],
    max_vertical_gap: float = 15.0
) -> List[str]:
    """
    Função utilitária para fundir fragmentos de fórmulas.

    Args:
        fragments: Lista de dicts com 'text', 'x0', 'y0', 'x1', 'y1'
        max_vertical_gap: Distância vertical máxima para fusão

    Returns:
        Lista de textos de fórmulas fundidas
    """
    # Converter para FormulaFragment
    frag_objects = [
        FormulaFragment(
            text=f.get('text', ''),
            x0=f.get('x0', 0),
            y0=f.get('y0', 0),
            x1=f.get('x1', 0),
            y1=f.get('y1', 0),
        )
        for f in fragments
    ]

    config = FormulaMergerConfig(max_vertical_gap=max_vertical_gap)
    merger = FormulaMerger(config)

    merged = merger.merge_fragments(frag_objects)

    return [m.text for m in merged]


def quick_merge(text_a: str, text_b: str) -> Tuple[bool, str]:
    """
    Verifica rapidamente se dois textos devem ser fundidos.

    Função simples para uso rápido sem coordenadas.

    Args:
        text_a: Primeiro texto
        text_b: Segundo texto

    Returns:
        Tupla (should_merge, merged_text)
    """
    merger = FormulaMerger()

    frag_a = FormulaFragment(text=text_a, y1=0)
    frag_b = FormulaFragment(text=text_b, y0=0)  # Simula proximidade

    should_merge, reason = merger._should_merge(frag_a, frag_b)

    if should_merge:
        merged = merger._merge_two(frag_a, frag_b, reason)
        return True, merged.text

    return False, text_a + " " + text_b


def is_incomplete_formula(text: str) -> bool:
    """
    Verifica se um texto representa uma fórmula incompleta.

    Args:
        text: Texto a verificar

    Returns:
        True se parece incompleto
    """
    merger = FormulaMerger()

    # Verificar delimitadores desbalanceados
    if merger._has_unbalanced_delimiters(text):
        return True

    # Verificar se termina com operador
    if merger._ends_with_operator(text):
        return True

    return False
