"""
Módulo de pós-processamento matemático avançado.

Este módulo corrige fórmulas matemáticas fragmentadas que resultam de PDFs onde
elementos de fórmulas (frações, expoentes, índices) são extraídos em ordem errada
ou separados em múltiplas linhas.

Problemas que resolve:
1. Frações verticais fragmentadas (numerador e denominador em linhas separadas)
2. Equações com elementos fora de ordem
3. Palavras grudadas ou separadas incorretamente em contexto matemático
4. Símbolos matemáticos isolados que deveriam estar junto a números/variáveis
5. Índices e expoentes separados de suas bases
6. Falta de espaços ao redor de símbolos gregos e matemáticos
7. Conversão para LaTeX de fórmulas matemáticas
8. Quebras de linha indevidas em exercícios/questões
"""

import re
from typing import List, Tuple, Dict, Optional, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MathPostprocessorConfig:
    """Configuração do pós-processador matemático."""
    # Ativar correção de frações fragmentadas
    fix_fractions: bool = True

    # Ativar correção de palavras grudadas
    fix_joined_words: bool = True

    # Ativar correção de palavras separadas
    fix_broken_words: bool = True

    # Ativar correção de equações
    fix_equations: bool = True

    # Ativar limpeza de fragmentos órfãos
    clean_orphan_fragments: bool = True

    # Número máximo de linhas para analisar juntas
    max_lookahead_lines: int = 3

    # Modo verboso para debug
    verbose: bool = False


class MathPostprocessor:
    """
    Pós-processador avançado para fórmulas matemáticas em Markdown.
    """

    # Símbolos gregos que precisam de espaço ao redor
    GREEK_LETTERS = 'αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩρμγνεσπτφωαβδλθ'

    # Símbolos matemáticos Unicode
    MATH_SYMBOLS = '∞∑∫∂√≤≥≠≈∈∉⊂⊃∩∪→←↔⇒⇐⇔±×÷·∝∀∃∇∆'

    def __init__(self, config: Optional[MathPostprocessorConfig] = None):
        self.config = config or MathPostprocessorConfig()
        self.stats = {
            'fractions_fixed': 0,
            'equations_fixed': 0,
            'words_fixed': 0,
            'lines_merged': 0,
            'greek_spacing_fixed': 0,
            'latex_converted': 0,
            'line_breaks_fixed': 0,
        }

    def process(self, text: str) -> str:
        """
        Processa texto completo aplicando todas as correções.

        Args:
            text: Texto Markdown a processar

        Returns:
            Texto corrigido
        """
        if not text:
            return text

        # Dividir em linhas para processamento
        lines = text.split('\n')

        # Fase 1: Correção de linhas individuais
        lines = [self._fix_line(line) for line in lines]

        # Fase 2: Correção de múltiplas linhas (frações, equações fragmentadas)
        lines = self._fix_multiline_fragments(lines)

        # Fase 3: Corrigir quebras de linha em exercícios/questões
        lines = self._fix_exercise_line_breaks(lines)

        # Fase 4: Limpeza de fragmentos órfãos
        if self.config.clean_orphan_fragments:
            lines = self._clean_orphan_fragments(lines)

        # Fase 5: Correção final de padrões conhecidos (REMOVIDO - tratamento específico)
        text = '\n'.join(lines)

        # Fase 6: Corrigir espaçamento ao redor de símbolos gregos
        text = self._fix_greek_spacing(text)

        # Fase 7: Corrigir palavras grudadas com símbolos
        text = self._fix_symbol_word_joining(text)

        # Fase 8: Converter fórmulas para LaTeX (opcional)
        text = self._convert_to_latex(text)

        return text

    def _fix_line(self, line: str) -> str:
        """Corrige problemas em uma única linha."""
        if not line.strip():
            return line

        original = line

        # Corrigir palavras grudadas em contexto comum
        if self.config.fix_joined_words:
            line = self._fix_joined_words(line)

        # Corrigir palavras quebradas
        if self.config.fix_broken_words:
            line = self._fix_broken_words_in_line(line)

        # Corrigir padrões de equações inline
        if self.config.fix_equations:
            line = self._fix_inline_equations(line)

        # Corrigir frações inline
        if self.config.fix_fractions:
            line = self._fix_inline_fractions(line)

        if line != original and self.config.verbose:
            logger.debug(f"Line fixed: '{original}' -> '{line}'")

        return line

    def _fix_joined_words(self, text: str) -> str:
        """
        Corrige palavras que foram grudadas incorretamente.

        Exemplos:
        - "fluidostrata" -> "fluidos trata"
        - "Oconceito" -> "O conceito"
        - "definirfluido" -> "definir fluido"
        """
        # Padrões de artigos/preposições grudados com substantivos
        patterns = [
            # "Oconceito" -> "O conceito"
            (r'\b([OAU])(conceito|fluido|líquido|gás|volume|peso|valor|módulo|sistema|princípio|equação)\b',
             r'\1 \2'),
            # "Amecânica" -> "A mecânica"
            (r'\b([AO])(mecânica|pressão|força|energia|massa|densidade|viscosidade|temperatura|área|altura)\b',
             r'\1 \2'),
            # "Éa" -> "É a"
            (r'\b(É)(a|o|um|uma)\b', r'\1 \2'),
            # "fluidos trata" (quando grudado)
            (r'\b(fluidos?)(trata|comporta|escoa|deforma)\b', r'\1 \2'),
            # Verbos no infinitivo grudados com substantivos
            (r'\b(definir|calcular|determinar|medir|analisar|obter|encontrar)(fluido|pressão|volume|massa|energia|força|valor)\b',
             r'\1 \2'),
            # Substantivo + verbo grudado
            (r'\b(fluido|líquido|gás)(define|escoa|deforma|comporta)\b', r'\1 \2'),
            # "pormenor" quando deveria ser "por menor"
            (r'\b(por)(menor|maior)\b', r'\1 \2'),
            # Unidades grudadas
            (r'(\d+)(kgf|kg|N|Pa|atm|mmHg|m²|m³|cm²|cm³)\b', r'\1 \2'),
        ]

        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    def _fix_broken_words_in_line(self, text: str) -> str:
        """
        Corrige palavras com espaços no meio.

        Exemplos:
        - "P rofessora" -> "Professora"
        - "F ederal" -> "Federal"
        """
        # Palavras específicas conhecidas
        specific_fixes = {
            r'\bF\s+ederal\b': 'Federal',
            r'\bU\s+niversidade\b': 'Universidade',
            r'\bJ\s+uiz\b': 'Juiz',
            r'\bF\s+ora\b': 'Fora',
            r'\bF\s+aculdade\b': 'Faculdade',
            r'\bE\s+ngenharia\b': 'Engenharia',
            r'\bP\s+rofessor\b': 'Professor',
            r'\bP\s+rofª\b': 'Profª',
            r'\bE\s+quilíbrio\b': 'Equilíbrio',
            r'\bE\s+studos\b': 'Estudos',
            r'\bT\s+ransporte\b': 'Transporte',
            r'\bC\s+álculo\b': 'Cálculo',
            r'\bP\s+ropriedade\b': 'Propriedade',
            r'\bA\s+ção\b': 'Ação',
            r'\bI\s+nstalações\b': 'Instalações',
            r'\bD\s+ensidade\b': 'Densidade',
            r'\bV\s+iscosidade\b': 'Viscosidade',
            r'\bT\s+emperatura\b': 'Temperatura',
            r'\bP\s+ressão\b': 'Pressão',
            r'\bM\s+ecânica\b': 'Mecânica',
            r'\bH\s+idrostática\b': 'Hidrostática',
            r'\bA\s+tmosférica\b': 'Atmosférica',
            r'\bM\s+anométrica\b': 'Manométrica',
            r'\bA\s+bsoluta\b': 'Absoluta',
        }

        for pattern, replacement in specific_fixes.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Padrão genérico: letra maiúscula + espaço + letras minúsculas
        text = re.sub(r'\b([A-ZÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ])\s+([a-záéíóúàèìòùâêîôûãõç]{3,})\b',
                      r'\1\2', text)

        self.stats['words_fixed'] += 1
        return text

    def _fix_inline_equations(self, text: str) -> str:
        """
        Corrige equações inline que foram fragmentadas.

        Exemplos:
        - "ρ = m/V m−massa/volume ρ = sendo V−" -> "ρ = m/V (sendo m = massa, V = volume)"
        """
        # Padrão: variável = fração seguida de "sendo" com definições
        pattern = r'(\w+)\s*=\s*(\w+)/(\w+)\s+(\w+)−(\w+)/(\w+)\s+\1\s*=\s*sendo\s+(\w+)−'

        def fix_equation(match):
            var = match.group(1)
            num = match.group(2)
            den = match.group(3)
            return f'{var} = {num}/{den} (sendo {num} = {match.group(5)}, {den} = ...)'

        text = re.sub(pattern, fix_equation, text)

        # Corrigir "= sendo" isolado
        text = re.sub(r'\s+=\s+sendo\s+', ' sendo ', text)

        # Corrigir repetições de variável isoladas
        text = re.sub(r'(\b[ρμγνε]\b)\s+\1', r'\1', text)

        return text

    def _fix_inline_fractions(self, text: str) -> str:
        """
        Corrige frações inline que foram fragmentadas.

        Exemplos:
        - "P/T = P/T" duplicado -> "P₁/T₁ = P₂/T₂"
        - "m/M n=" -> "n = m/M"
        """
        # Remover duplicatas de frações
        text = re.sub(r'(\w+/\w+)\s+\1\b', r'\1', text)

        # Corrigir padrão "fração variável=" -> "variável = fração"
        text = re.sub(r'(\d+/\d+|\w/\w)\s+([a-zA-Z])\s*=\s*$', r'\2 = \1', text)

        return text

    def _fix_greek_spacing(self, text: str) -> str:
        """
        Corrige espaçamento ao redor de símbolos gregos.

        Exemplos:
        - "entreρeγ" -> "entre ρ e γ"
        - "valordeρ" -> "valor de ρ"
        """
        # Padrão: palavra + símbolo grego (sem espaço)
        for greek in self.GREEK_LETTERS:
            # Adicionar espaço antes do símbolo grego quando precedido por letra
            text = re.sub(rf'([a-zA-ZáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ])({greek})', r'\1 \2', text)
            # Adicionar espaço depois do símbolo grego quando seguido por letra
            text = re.sub(rf'({greek})([a-zA-ZáéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ])', r'\1 \2', text)
            self.stats['greek_spacing_fixed'] += 1

        # Corrigir padrões específicos comuns
        text = re.sub(r'\bentre\s*([ρμγνεσπτφωαβδλθ])\s*e\s*([ρμγνεσπτφωαβδλθ])\b', r'entre \1 e \2', text)

        # Corrigir "Relação entreXeY" -> "Relação entre X e Y"
        text = re.sub(r'Relação\s+entre\s*(\S+)\s*e\s*(\S+)', r'Relação entre \1 e \2', text)

        return text

    def _fix_symbol_word_joining(self, text: str) -> str:
        """
        Corrige palavras grudadas com símbolos matemáticos.

        Exemplos:
        - "valordeε" -> "valor de ε"
        - "móduloε" -> "módulo ε"
        """
        # Palavras comuns que aparecem grudadas com símbolos
        words_before_symbols = [
            'valor', 'módulo', 'coeficiente', 'constante', 'variável',
            'função', 'equação', 'fórmula', 'expressão', 'relação',
            'entre', 'para', 'com', 'por', 'sobre', 'sob',
        ]

        for word in words_before_symbols:
            # Padrão: palavra + símbolo (sem espaço)
            pattern = rf'\b({word})([{self.GREEK_LETTERS}{self.MATH_SYMBOLS}])'
            text = re.sub(pattern, r'\1 \2', text, flags=re.IGNORECASE)

        return text

    def _fix_exercise_line_breaks(self, lines: List[str]) -> List[str]:
        """
        Corrige quebras de linha indevidas em exercícios/questões.

        Exemplos:
        - "b)\n\n𝑓(2) = ?" -> "b) 𝑓(2) = ?"
        - "c)\n\n𝑓(−1) = ?" -> "c) 𝑓(−1) = ?"
        """
        if not lines:
            return lines

        result = []
        i = 0

        while i < len(lines):
            current = lines[i].strip()

            # Detectar padrão de letra de item seguida de linha(s) vazia(s) e então conteúdo
            # Padrão: "a)" ou "b)" ou "1." ou "2)" etc.
            item_pattern = re.match(r'^([a-zA-Z]\)|[0-9]+[\.\)])\s*$', current)

            if item_pattern:
                # Procurar próxima linha não vazia
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1

                if j < len(lines):
                    next_content = lines[j].strip()
                    # Se a próxima linha tem conteúdo relevante, juntar
                    if next_content and not re.match(r'^([a-zA-Z]\)|[0-9]+[\.\)])\s*$', next_content):
                        # Juntar item com seu conteúdo
                        merged = f"{current} {next_content}"
                        result.append(merged)
                        self.stats['line_breaks_fixed'] += 1
                        i = j + 1
                        continue

            result.append(lines[i])
            i += 1

        return result

    def _convert_to_latex(self, text: str) -> str:
        """
        Converte fórmulas matemáticas para formato LaTeX.

        Detecta padrões matemáticos e os envolve em delimitadores LaTeX.
        """
        # Converter frações simples para LaTeX
        # Padrão: a/b onde a e b são números ou variáveis simples
        def fraction_to_latex(match):
            num = match.group(1)
            den = match.group(2)
            # Só converter se parecer uma fração matemática real
            if len(num) <= 3 and len(den) <= 3:
                self.stats['latex_converted'] += 1
                return f'$\\frac{{{num}}}{{{den}}}$'
            return match.group(0)

        # NOTA: Conversão de frações para LaTeX desabilitada temporariamente
        # pois pode quebrar paths de imagens e outras referências
        # text = re.sub(r'(?<![/\w])([a-zA-Z0-9]+)/([a-zA-Z0-9]+)(?![/\w])', fraction_to_latex, text)

        # =============================================
        # 1. Primeiro: Converter letras matemáticas Unicode (itálico) para ASCII
        # Estas são as letras 𝑎, 𝑏, 𝑐, ... 𝑧, 𝐴, 𝐵, ... 𝑍
        # =============================================
        math_italic_lower = {
            '𝑎': 'a', '𝑏': 'b', '𝑐': 'c', '𝑑': 'd', '𝑒': 'e', '𝑓': 'f', '𝑔': 'g',
            'ℎ': 'h', '𝑖': 'i', '𝑗': 'j', '𝑘': 'k', '𝑙': 'l', '𝑚': 'm', '𝑛': 'n',
            '𝑜': 'o', '𝑝': 'p', '𝑞': 'q', '𝑟': 'r', '𝑠': 's', '𝑡': 't', '𝑢': 'u',
            '𝑣': 'v', '𝑤': 'w', '𝑥': 'x', '𝑦': 'y', '𝑧': 'z',
        }
        math_italic_upper = {
            '𝐴': 'A', '𝐵': 'B', '𝐶': 'C', '𝐷': 'D', '𝐸': 'E', '𝐹': 'F', '𝐺': 'G',
            '𝐻': 'H', '𝐼': 'I', '𝐽': 'J', '𝐾': 'K', '𝐿': 'L', '𝑀': 'M', '𝑁': 'N',
            '𝑂': 'O', '𝑃': 'P', '𝑄': 'Q', '𝑅': 'R', '𝑆': 'S', '𝑇': 'T', '𝑈': 'U',
            '𝑉': 'V', '𝑊': 'W', '𝑋': 'X', '𝑌': 'Y', '𝑍': 'Z',
        }

        # Converter todas as letras matemáticas itálico para ASCII
        for italic, ascii_char in {**math_italic_lower, **math_italic_upper}.items():
            text = text.replace(italic, ascii_char)

        # =============================================
        # 2. Converter símbolos gregos para LaTeX
        # =============================================
        greek_to_latex = {
            'α': r'\alpha', 'β': r'\beta', 'γ': r'\gamma', 'δ': r'\delta',
            'ε': r'\epsilon', 'ζ': r'\zeta', 'η': r'\eta', 'θ': r'\theta',
            'ι': r'\iota', 'κ': r'\kappa', 'λ': r'\lambda', 'μ': r'\mu',
            'ν': r'\nu', 'ξ': r'\xi', 'π': r'\pi', 'ρ': r'\rho',
            'σ': r'\sigma', 'τ': r'\tau', 'υ': r'\upsilon', 'φ': r'\phi',
            'χ': r'\chi', 'ψ': r'\psi', 'ω': r'\omega',
            'Γ': r'\Gamma', 'Δ': r'\Delta', 'Θ': r'\Theta', 'Λ': r'\Lambda',
            'Ξ': r'\Xi', 'Π': r'\Pi', 'Σ': r'\Sigma', 'Φ': r'\Phi',
            'Ψ': r'\Psi', 'Ω': r'\Omega',
        }

        # Converter equações que contêm símbolos gregos
        for greek, latex in greek_to_latex.items():
            # Padrão: símbolo grego em contexto de equação (com = ou outros operadores)
            pattern = rf'({greek})\s*='
            # Usar lambda para evitar problemas de escape com \
            latex_escaped = latex  # Capturar na closure
            text = re.sub(pattern, lambda m: f'${latex_escaped}$ =', text)

        # =============================================
        # 3. Converter subscritos e sobrescritos Unicode
        # =============================================
        # x₁, x₂ etc -> $x_1$, $x_2$
        subscript_map = {'₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
                         '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9'}
        superscript_map = {'⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
                          '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9'}

        for sub, num in subscript_map.items():
            # Usar função lambda para evitar problemas de escape
            text = re.sub(rf'([a-zA-Z]){sub}', lambda m: f'${m.group(1)}_{num}$', text)

        for sup, num in superscript_map.items():
            text = re.sub(rf'([a-zA-Z]){sup}', lambda m: f'${m.group(1)}^{num}$', text)

        # Converter ² e ³ para LaTeX
        text = re.sub(r'(\w)²', lambda m: f'${m.group(1)}^2$', text)
        text = re.sub(r'(\w)³', lambda m: f'${m.group(1)}^3$', text)

        # =============================================
        # 4. Detectar e envolver expressões matemáticas em $...$
        # Agora que os caracteres Unicode foram convertidos para ASCII,
        # podemos detectar padrões como: f(x) = 2x + 1, x^2, sqrt(x), etc.
        # =============================================

        # Converter √expressões diretamente para LaTeX ANTES de detectar equações
        # Padrão: √conteúdo onde conteúdo pode ter letras, números, operadores
        # Ex: √x, √x−3, √(x+1)
        # O Unicode minus (U+2212) pode aparecer após a variável

        # Primeiro: √(conteúdo) com parênteses
        text = re.sub(
            r'√\(([^)]+)\)',
            lambda m: f'$\\sqrt{{{m.group(1).strip()}}}$',
            text
        )

        # Segundo: √variável ou √número (sem parênteses)
        # Incluir Unicode minus (−) e ASCII minus (-)
        text = re.sub(
            r'√([a-zA-Z0-9\−\-])',
            lambda m: f'$\\sqrt{{{m.group(1)}}}$',
            text
        )

        # Detectar equações com = (mas não dentro de delimitadores existentes)
        def wrap_equation(match):
            eq = match.group(0)
            # Não envolver se já está dentro de $
            if '$' not in eq:
                self.stats['latex_converted'] += 1
                return f'${eq}$'
            return eq

        # Padrão para equações: variáveis, operadores, =, etc.
        # Ex: f(x) = 2x + 1, x^2 + y^2 = 1
        text = re.sub(
            r'(?<!\$)([a-zA-Z]\([a-zA-Z]\)\s*=\s*[a-zA-Z0-9\s\+\-\*\/\^\[\]\(\)]+|[a-zA-Z]\s*\^\s*\d+)(?![\$])',
            wrap_equation, text
        )

        return text

    def _fix_multiline_fragments(self, lines: List[str]) -> List[str]:
        """
        Corrige fragmentos que se estendem por múltiplas linhas.

        Detecta padrões como:
        - Linha N: "e) 𝑓("
        - Linha N+1: "3. = ?"
        E junta em: "e) 𝑓(1/3) = ?"
        """
        if not lines:
            return lines

        result = []
        i = 0

        while i < len(lines):
            current = lines[i]
            merged = False

            # Tentar merge com próximas linhas
            for lookahead in range(1, min(self.config.max_lookahead_lines + 1, len(lines) - i)):
                next_lines = lines[i + 1:i + 1 + lookahead]

                merged_line = self._try_merge_lines(current, next_lines)
                if merged_line is not None:
                    result.append(merged_line)
                    i += 1 + lookahead
                    merged = True
                    self.stats['lines_merged'] += lookahead
                    break

            if not merged:
                result.append(current)
                i += 1

        return result

    def _try_merge_lines(self, current: str, next_lines: List[str]) -> Optional[str]:
        """
        Tenta mesclar linhas se detectar fragmentação.

        Returns:
            Linha mesclada ou None se não deve mesclar
        """
        if not next_lines:
            return None

        next_line = next_lines[0].strip()
        current_stripped = current.strip()

        # Padrão 1: função incompleta + denominador
        # "e) 𝑓(" + "3. = ?" -> "e) 𝑓(1/3) = ?"
        if re.search(r'[𝑓fFgGhH]\s*\(\s*$', current_stripped):
            match = re.match(r'^(\d+)\.\s*=\s*\?(.*)$', next_line)
            if match:
                denominator = match.group(1)
                rest = match.group(2)
                return current_stripped + f"1/{denominator}) = ?{rest}"

        # Padrão 2: fração isolada + função vazia
        fraction_match = re.match(r'^\s*(\d+/\d+)\s*$', current_stripped)
        if fraction_match:
            func_match = re.search(r'([𝑓fFgGhH])\s*\(\s*\)\s*=\s*\?', next_line)
            if func_match:
                fraction = fraction_match.group(1)
                func_char = func_match.group(1)
                fixed = re.sub(
                    r'([𝑓fFgGhH])\s*\(\s*\)\s*=\s*\?',
                    f'{func_char}({fraction}) = ?',
                    next_line
                )
                return fixed

        # Padrão 3: "letra) fração" + "função() = ?"
        letter_frac = re.match(r'^([a-e]\))\s*(\d+/\d+)\s*$', current_stripped)
        if letter_frac:
            func_match = re.search(r'([𝑓fFgGhH])\s*\(\s*\)\s*=\s*\?', next_line)
            if func_match:
                letter = letter_frac.group(1)
                fraction = letter_frac.group(2)
                func_char = func_match.group(1)
                return f"{letter} {func_char}({fraction}) = ?"

        # Padrão 4: equação fragmentada com "sendo"
        # "ρ = m/V" + "sendo m = massa, V = volume"
        if re.search(r'=\s*\w+/\w+\s*$', current_stripped):
            if next_line.lower().startswith('sendo'):
                return f"{current_stripped} ({next_line})"

        # Padrão 5: linha termina com operador
        if re.search(r'[+\-×÷=]\s*$', current_stripped):
            if re.match(r'^[\d\w(]', next_line):
                return f"{current_stripped} {next_line}"

        # Padrão 6: linha é apenas um número/variável que parece numerador
        if re.match(r'^[\d\w]+$', current_stripped) and len(current_stripped) < 5:
            # Verificar se próxima linha parece denominador
            if re.match(r'^[\d\w]+\s*[=<>]', next_line) or re.match(r'^[\d\w]+$', next_line):
                # Pode ser fração - verificar contexto
                pass  # Por segurança, não mesclar automaticamente

        return None

    def _clean_orphan_fragments(self, lines: List[str]) -> List[str]:
        """
        Remove fragmentos órfãos que não fazem sentido isolados.

        Exemplos de fragmentos a remover:
        - Linhas com apenas "/" ou "="
        - Linhas com apenas um símbolo matemático isolado
        - Linhas que são claramente continuação perdida
        """
        orphan_patterns = [
            r'^\s*[/=+\-×÷]\s*$',  # Apenas operador
            r'^\s*\(\s*\)\s*$',     # Parênteses vazios
            r'^\s*sendo\s*$',       # "sendo" isolado
            r'^\s*onde:?\s*$',      # "onde" isolado
        ]

        result = []
        for line in lines:
            is_orphan = False
            for pattern in orphan_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    is_orphan = True
                    break

            if not is_orphan:
                result.append(line)

        return result

    def _fix_known_patterns(self, text: str) -> str:
        """
        Aplica correções para padrões conhecidos de erros.
        """
        # =================================================================
        # CORREÇÕES DE ESPAÇAMENTO EM FÓRMULAS
        # =================================================================

        # Corrigir "G/V m/V γ = = g" e padrões similares
        text = re.sub(r'G/V\s+m/V\s+γ\s*=\s*=\s*g', 'γ = G/V = m·g/V = ρg', text)

        # Corrigir equações com múltiplos "=" fragmentados
        text = re.sub(r'=\s+=\s+', '= ', text)
        text = re.sub(r'=\s+=', '=', text)

        # Corrigir "⇒γ = ρg" -> "⇒ γ = ρg"
        text = re.sub(r'⇒([a-zA-Zρμγνεσπτφωαβδλθ])', r'⇒ \1', text)

        # =================================================================
        # CORREÇÕES ESPECÍFICAS PARA FÓRMULAS DE MECÂNICA DOS FLUIDOS
        # =================================================================

        # Fórmula de massa específica (densidade): ρ = m/V
        text = re.sub(
            r'm/V\s+m−massa/volume\s+ρ\s*=?\s*sendo\s+V−',
            'ρ = m/V (sendo m = massa, V = volume)',
            text
        )
        text = re.sub(
            r'ρ\s*=?\s*sendo\s+V−.*?([\n\r]|$)',
            r'ρ = m/V\1',
            text
        )

        # Fórmula de peso específico: γ = G/V
        text = re.sub(
            r'G/V\s+G/V\s*−peso/volume\s+γ\s*=\s*sendo',
            'γ = G/V (sendo G = peso, V = volume)',
            text
        )
        text = re.sub(
            r'G/V\s*−peso/volume\s+γ\s*=\s*sendo',
            'γ = G/V (sendo G = peso, V = volume)',
            text
        )

        # Fórmula de volume específico fragmentada
        text = re.sub(
            r'V/G\s+1\s+G/V\s*−peso/volume\s+V\s*=?\s*sendo',
            'V = 1/γ (sendo V = volume específico, γ = peso específico)',
            text
        )
        text = re.sub(
            r'G/V\s*−peso/volume\s+V\s+sendo',
            'V = 1/γ (V = volume específico)',
            text
        )

        # Corrigir padrões de "sendo" fragmentados
        text = re.sub(r'\s+=\s*sendo\s+', ' sendo ', text)
        text = re.sub(r'sendo\s+(\w)−', r'sendo \1 = ', text)

        # Corrigir padrões de sistemas de unidades fragmentados
        text = re.sub(
            r'm/kgf3\s+Sistema/Sistema\s+MK/MKS\*S:\s*γ\s*=\s*kgf/m\s+segue:\s*3/N',
            'Sistema MKS*: γ em m³/kgf; Sistema MKS: γ em m³/N',
            text
        )
        text = re.sub(
            r'N/cm\s+cm/d\s*3\s*:\s*γ\s*=',
            'Sistema CGS: γ em cm³/dyn',
            text
        )

        # Sistema de unidades fragmentado
        text = re.sub(
            r'Sistema/Sistema\s+MK\*?S',
            'Sistema MKS',
            text
        )
        text = re.sub(
            r'Sistema/Sistema\s+MKS/C\.G\.S\.',
            'Sistema MKS (C.G.S.)',
            text
        )
        text = re.sub(
            r'Sistema\s+MKS\s*/\s*C\.G\.S\.',
            'Sistema MKS (C.G.S.)',
            text
        )
        text = re.sub(
            r'Sistema/Sistema\s+MK/MKS\*S',
            'Sistema MKS/MKS*',
            text
        )

        # Corrigir fórmulas de comprimento/velocidade fragmentadas
        text = re.sub(
            r'LV/2\s+L/V−\s*compriment/velocidade\s*\(m\)\s*=',
            'L = comprimento (m), V = velocidade (m/s)',
            text
        )
        text = re.sub(
            r'(\w)−\s*compriment',
            r'\1 = comprimento',
            text
        )
        text = re.sub(
            r'(\w)−\s*velocidade',
            r'\1 = velocidade',
            text
        )
        text = re.sub(
            r'(\w)−\s*diâmetro',
            r'\1 = diâmetro',
            text
        )

        # Fórmula de densidade fragmentada
        text = re.sub(
            r'ρ\s*=\s*m/V\s+m−massa/volume\s+ρ\s*=\s*sendo\s+V−',
            'ρ = m/V (sendo m = massa, V = volume)',
            text
        )

        # Fórmula de peso específico fragmentada
        text = re.sub(
            r'γ\s*=\s*G/V\s+G−peso/volume\s+γ\s*=\s*sendo\s+V−',
            'γ = G/V (sendo G = peso, V = volume)',
            text
        )

        # Remover repetições de símbolos gregos
        text = re.sub(r'([ρμγνεσπτφωαβδλθ])\s+\1\b', r'\1', text)

        # Corrigir "kgf/m Sistema" -> "kgf/m³"
        text = re.sub(r'kgf/m\s+Sistema', 'kgf/m³', text)

        # =================================================================
        # CORREÇÕES DE UNIDADES E EXPONENTES
        # =================================================================

        # Corrigir exponentes soltos
        text = re.sub(r'\bm\s*2\b', 'm²', text)
        text = re.sub(r'\bm\s*3\b', 'm³', text)
        text = re.sub(r'\bcm\s*2\b', 'cm²', text)
        text = re.sub(r'\bcm\s*3\b', 'cm³', text)

        # Corrigir "N/m 2" -> "N/m²"
        text = re.sub(r'N/m\s+2\b', 'N/m²', text)
        text = re.sub(r'N/m\s+3\b', 'N/m³', text)

        # Corrigir unidades com frações
        text = re.sub(r'kgf/m\s*2\b', 'kgf/m²', text)
        text = re.sub(r'kgf/m\s*3\b', 'kgf/m³', text)
        text = re.sub(r'm/s\s*2\b', 'm/s²', text)
        text = re.sub(r'kg/m\s*3\b', 'kg/m³', text)

        # Corrigir temperaturas
        text = re.sub(r'(\d+)\s*º\s*C\b', r'\1°C', text)
        text = re.sub(r'(\d+)\s*º\s*K\b', r'\1K', text)

        # =================================================================
        # CORREÇÕES DE PALAVRAS GRUDADAS COMUNS
        # =================================================================

        # Artigos grudados com palavras (contexto PDF técnico)
        text = re.sub(r'\bOconceito\b', 'O conceito', text)
        text = re.sub(r'\bOpeso\b', 'O peso', text)
        text = re.sub(r'\bOvolume\b', 'O volume', text)
        text = re.sub(r'\bOmódulo\b', 'O módulo', text)
        text = re.sub(r'\bOnúmero\b', 'O número', text)
        text = re.sub(r'\bOfluido\b', 'O fluido', text)
        text = re.sub(r'\bOescoamento\b', 'O escoamento', text)
        text = re.sub(r'\bOcentro\b', 'O centro', text)
        text = re.sub(r'\bOcálculo\b', 'O cálculo', text)
        text = re.sub(r'\bOresultado\b', 'O resultado', text)
        text = re.sub(r'\bOvalor\b', 'O valor', text)
        text = re.sub(r'\bOsistema\b', 'O sistema', text)
        text = re.sub(r'\bOprincípio\b', 'O princípio', text)
        text = re.sub(r'\bOtermo\b', 'O termo', text)
        text = re.sub(r'\bOcampo\b', 'O campo', text)
        text = re.sub(r'\bOsomatório\b', 'O somatório', text)

        # Corrigir OBS sem espaço
        text = re.sub(r'\bOBS:\s*Relação\s+entre([ρμγνεσπτφωαβδλθ])e([ρμγνεσπτφωαβδλθ])\b',
                      r'OBS: Relação entre \1 e \2', text)
        text = re.sub(r'\bAmecânica\b', 'A mecânica', text)
        text = re.sub(r'\bAequação\b', 'A equação', text)
        text = re.sub(r'\bAcompressibilidade\b', 'A compressibilidade', text)
        text = re.sub(r'\bApressão\b', 'A pressão', text)
        text = re.sub(r'\bAforça\b', 'A força', text)
        text = re.sub(r'\bArelação\b', 'A relação', text)
        text = re.sub(r'\bAtemperatura\b', 'A temperatura', text)
        text = re.sub(r'\bAatmosfera\b', 'A atmosfera', text)
        text = re.sub(r'\bAtensão\b', 'A tensão', text)
        text = re.sub(r'\bAunidade\b', 'A unidade', text)
        text = re.sub(r'\bAintegral\b', 'A integral', text)
        text = re.sub(r'\bAcomponente\b', 'A componente', text)
        text = re.sub(r'\bAposição\b', 'A posição', text)
        text = re.sub(r'\bAárea\b', 'A área', text)
        text = re.sub(r'\bAaltura\b', 'A altura', text)
        text = re.sub(r'\bAdistância\b', 'A distância', text)
        text = re.sub(r'\bAvelocidade\b', 'A velocidade', text)
        text = re.sub(r'\bAvazão\b', 'A vazão', text)
        text = re.sub(r'\bAfigura\b', 'A figura', text)
        text = re.sub(r'\bAexpressão\b', 'A expressão', text)
        text = re.sub(r'\bAfórmula\b', 'A fórmula', text)
        text = re.sub(r'\bAdefinição\b', 'A definição', text)

        # Preposições/artigos com substantivos técnicos
        text = re.sub(r'\bde(capilaridade|compressibilidade|viscosidade|elasticidade)\b', r'de \1', text)

        # Padrão genérico para palavras com O/A grudados (contexto técnico)
        # NOTA: Desabilitado pois quebra palavras válidas como "Autora", "Ambiental", "Aerodinâmica"
        # Usar apenas padrões específicos listados acima
        # text = re.sub(r'\b([OA])([a-záéíóúàèìòùâêîôûãõç]{5,})\b',
        #               lambda m: m.group(1) + ' ' + m.group(2) if m.group(2)[0].islower() else m.group(0),
        #               text)

        # Lista de palavras que NÃO devem ser separadas (começam com A/O mas são palavras válidas)
        # Estas são exceções ao padrão de separação
        words_to_keep = [
            'Autora', 'Autor', 'Ambiental', 'Aerodinâmica', 'Aplicação', 'Aplicando',
            'Absoluta', 'Absoluto', 'Azevedo', 'Arquimedes', 'Assim', 'Ainda',
            'Onde', 'Outro', 'Outra', 'Outros', 'Outras',
        ]

        # Restaurar palavras que foram incorretamente separadas
        for word in words_to_keep:
            # Corrigir "A utora" -> "Autora", "A mbiental" -> "Ambiental"
            broken = word[0] + ' ' + word[1:]
            text = re.sub(rf'\b{broken}\b', word, text)

        # Padrões específicos de definições fragmentadas "X− descrição"
        text = re.sub(r'(\w)\s*−\s*(massa|volume|peso|pressão|temperatura|velocidade|comprimento|diâmetro|área|altura)\b',
                      r'\1 = \2', text)

        # =================================================================
        # CORREÇÕES DE FUNÇÕES MATEMÁTICAS
        # =================================================================

        # Corrigir "𝑓(𝑥) = 2𝑥+ 1" -> "𝑓(𝑥) = 2𝑥 + 1" (espaço antes do +)
        text = re.sub(r'(\d)(\+|\-)', r'\1 \2', text)
        text = re.sub(r'(\+|\-)(\d)', r'\1 \2', text)

        # Corrigir espaços em torno de operadores em equações
        text = re.sub(r'([𝑥𝑦𝑧𝑎𝑏𝑐𝑓𝑔ℎ])(\+)', r'\1 \2', text)
        text = re.sub(r'(\+)([𝑥𝑦𝑧𝑎𝑏𝑐𝑓𝑔ℎ\d])', r'\1 \2', text)

        # =================================================================
        # LIMPEZA FINAL
        # =================================================================

        # Limpar espaços múltiplos
        text = re.sub(r'  +', ' ', text)

        # Limpar linhas com apenas símbolos/operadores isolados
        text = re.sub(r'^\s*[=+\-×÷]\s*$', '', text, flags=re.MULTILINE)

        return text

    def get_stats(self) -> Dict:
        """Retorna estatísticas de processamento."""
        return self.stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self.stats = {
            'fractions_fixed': 0,
            'equations_fixed': 0,
            'words_fixed': 0,
            'lines_merged': 0,
        }


def postprocess_math(text: str, config: Optional[MathPostprocessorConfig] = None) -> str:
    """
    Função utilitária para pós-processar texto matemático.

    Args:
        text: Texto a processar
        config: Configuração opcional

    Returns:
        Texto corrigido
    """
    processor = MathPostprocessor(config)
    return processor.process(text)


def fix_equation_fragments(lines: List[str]) -> List[str]:
    """
    Função utilitária para corrigir fragmentos de equações em lista de linhas.

    Args:
        lines: Lista de linhas

    Returns:
        Lista de linhas corrigidas
    """
    processor = MathPostprocessor()
    return processor._fix_multiline_fragments(lines)


def fix_fraction_notation(text: str) -> str:
    """
    Corrige notação de frações para formato consistente.

    Converte frações como "a sobre b" ou elementos verticais para "a/b".
    """
    # Padrão "num \n den" quando claramente fração
    text = re.sub(r'(\d+)\s*\n\s*(\d+)(?=\s*[=<>]|\s*$)', r'\1/\2', text)

    return text


def aggressive_formula_cleanup(text: str) -> str:
    """
    Limpeza agressiva de fórmulas fragmentadas.

    Este é um último recurso para corrigir padrões muito específicos
    que escapam das outras correções.
    """
    # Padrões muito específicos de PDFs técnicos brasileiros

    # Fórmula ρ = m/V fragmentada de várias formas
    patterns = [
        # "m/V m−massa/volume ρ = sendo V−" -> ρ = m/V
        (r'm/V\s+m[−\-]massa/volume\s+ρ\s*=?\s*sendo\s+V[−\-]',
         'ρ = m/V (m = massa, V = volume)'),

        # "G/V G/V −peso/volume γ= sendo" -> γ = G/V
        (r'G/V\s+G/V\s*[−\-]peso/volume\s+γ\s*=\s*sendo',
         'γ = G/V (G = peso, V = volume)'),

        # Equações de gases fragmentadas
        (r'P/R\s*-pressão/temperatuabsoluta/do',
         'P/(RT) onde: P = pressão, R = constante do gás, T = temperatura absoluta'),

        # Sistema/Sistema MK*S
        (r'Sistema/Sistema\s+MK\*S:\s*γ\s*=\s*m/33',
         'Sistema MKS: γ em kgf/m³'),

        # Padrão de H2O fragmentado
        (r'H\s*2\s*O', 'H₂O'),
        (r'H2O', 'H₂O'),

        # Corrigir subscritos numéricos comuns
        (r'\b([PTGV])(\d)\b', r'\1₍\2₎'),
    ]

    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def fix_technical_abbreviations(text: str) -> str:
    """
    Corrige abreviações técnicas fragmentadas.
    """
    abbreviations = {
        r'\bkg\s*f\b': 'kgf',
        r'\bm\s*m\s*Hg\b': 'mmHg',
        r'\bK\s*Pa\b': 'kPa',
        r'\bM\s*Pa\b': 'MPa',
        r'\bN\s*\.\s*m\b': 'N·m',
        r'\bN\s*\.\s*s\b': 'N·s',
    }

    for pattern, replacement in abbreviations.items():
        text = re.sub(pattern, replacement, text)

    return text


# Padrões específicos para documentos técnicos/científicos brasileiros
BRAZILIAN_TECHNICAL_PATTERNS = {
    # Universidades
    r'\bU\s*F\s*J\s*F\b': 'UFJF',
    r'\bU\s*F\s*M\s*G\b': 'UFMG',
    r'\bU\s*S\s*P\b': 'USP',
    r'\bU\s*N\s*I\s*C\s*A\s*M\s*P\b': 'UNICAMP',

    # Unidades
    r'\bkg\s*f\b': 'kgf',
    r'\bm\s*/\s*s\s*²\b': 'm/s²',
    r'\bN\s*/\s*m\s*²\b': 'N/m²',
    r'\bPa\s*scal\b': 'Pascal',

    # Termos técnicos
    r'\bHidro\s*stática\b': 'Hidrostática',
    r'\bHidro\s*dinâmica\b': 'Hidrodinâmica',
    r'\bTermo\s*dinâmica\b': 'Termodinâmica',
}


def apply_brazilian_fixes(text: str) -> str:
    """
    Aplica correções específicas para documentos técnicos brasileiros.
    """
    for pattern, replacement in BRAZILIAN_TECHNICAL_PATTERNS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Aplicar limpeza agressiva de fórmulas
    text = aggressive_formula_cleanup(text)

    # Corrigir abreviações técnicas
    text = fix_technical_abbreviations(text)

    # Corrigir espaçamento em "entre X e Y" com símbolos gregos
    text = re.sub(r'entre\s*([ρμγνεσπτφωαβδλθΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ])\s*e\s*([ρμγνεσπτφωαβδλθΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ])',
                  r'entre \1 e \2', text)

    return text


def merge_broken_exercise_items(text: str) -> str:
    """
    Mescla itens de exercícios que foram quebrados em múltiplas linhas.

    Exemplo:
    "b)

    𝑓(2) = ?"

    Vira:
    "b) 𝑓(2) = ?"
    """
    lines = text.split('\n')
    result = []
    i = 0

    while i < len(lines):
        current = lines[i].strip()

        # Padrão de item: a), b), c), 1., 2., etc
        if re.match(r'^[a-zA-Z]\)$|^\d+[\.\)]$', current):
            # Procurar conteúdo nas próximas linhas
            content_lines = []
            j = i + 1

            # Pular linhas vazias
            while j < len(lines) and not lines[j].strip():
                j += 1

            # Coletar conteúdo até próximo item ou linha vazia dupla
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line:
                    break
                if re.match(r'^[a-zA-Z]\)$|^\d+[\.\)]$', next_line):
                    break
                content_lines.append(next_line)
                j += 1

            if content_lines:
                merged = current + ' ' + ' '.join(content_lines)
                result.append(merged)
                i = j
                continue

        result.append(lines[i])
        i += 1

    return '\n'.join(result)
