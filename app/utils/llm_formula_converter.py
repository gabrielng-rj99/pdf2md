"""
Módulo de conversão de fórmulas matemáticas usando LLM local leve.

Este módulo usa modelos de linguagem pequenos (< 4GB RAM por padrão) para
converter fórmulas matemáticas de texto extraído de PDF para LaTeX formatado.

Vantagens sobre regex:
1. Entende contexto - não converte texto normal
2. Preserva estrutura de parênteses e frações
3. Gera LaTeX válido e bem formatado
4. Detecta limites corretos das fórmulas

Modelos suportados (em ordem de preferência por RAM):
- Qwen2.5-0.5B-Instruct (~1GB RAM)
- Qwen2.5-1.5B-Instruct (~3GB RAM)
- Qwen2.5-3B-Instruct (~6GB RAM)
- Phi-3-mini-4k-instruct (~4GB RAM)

Configuração de RAM:
- RAM_LIMIT_GB = 4 (padrão, ajustável)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Generator
from enum import Enum
import os

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAÇÃO DE RAM - AJUSTE AQUI
# =============================================================================

# Limite de RAM em GB para o modelo LLM
# Ajuste conforme sua disponibilidade de memória
RAM_LIMIT_GB: float = 4.0

# Variável de ambiente para override
_env_ram = os.environ.get('PDF2MD_LLM_RAM_LIMIT_GB')
if _env_ram:
    try:
        RAM_LIMIT_GB = float(_env_ram)
    except ValueError:
        pass


class ModelSize(Enum):
    """Tamanhos de modelo disponíveis."""
    TINY = "tiny"       # ~1GB RAM (0.5B params)
    SMALL = "small"     # ~3GB RAM (1.5B params)
    MEDIUM = "medium"   # ~6GB RAM (3B params)
    LARGE = "large"     # ~8GB RAM (7B params)


@dataclass
class LLMConfig:
    """Configuração do conversor LLM."""
    # Limite de RAM em GB
    ram_limit_gb: float = RAM_LIMIT_GB

    # Modelo específico (opcional, senão auto-seleciona)
    model_name: Optional[str] = None

    # Comportamento
    batch_size: int = 10           # Linhas por batch
    max_line_length: int = 500     # Máximo de caracteres por linha
    timeout_seconds: int = 30      # Timeout por batch

    # Cache
    use_cache: bool = True
    cache_size: int = 1000

    # Fallback
    fallback_to_original: bool = True  # Se LLM falhar, manter original

    # Device - PRIORIZA GPU
    device: str = "auto"  # "auto", "cpu", "cuda", "mps"
    prefer_gpu: bool = True  # Sempre tentar GPU primeiro

    # Quantização - permite usar modelos maiores com menos VRAM
    use_quantization: bool = True  # Usar 4-bit quando possível

    # GPU memory fraction (0.0-1.0) - quanto da VRAM usar
    gpu_memory_fraction: float = 0.9


# =============================================================================
# FUNÇÕES DE ESPAÇAMENTO DE SÍMBOLOS MATEMÁTICOS
# =============================================================================

# Símbolos matemáticos que precisam de espaço antes quando grudados em texto
MATH_FUNCTION_SYMBOLS = {
    '𝑓', '𝑔', '𝑥', '𝑦', '𝑧', '𝑎', '𝑏', '𝑐', '𝑛', '𝑚', '𝑘',
    'ƒ',  # f alternativo
}

# Padrões para detectar fórmulas inline grudadas no texto
INLINE_FORMULA_PATTERNS = [
    # função𝑓(𝑥) -> função 𝑓(𝑥)
    (re.compile(r'([a-záàâãéêíóôõúç])([𝑓𝑔𝑥𝑦𝑧𝑎𝑏𝑐𝑛𝑚𝑘ƒ]\([^)]+\))', re.IGNORECASE), r'\1 \2'),
    # texto𝑓(𝑥) = -> texto 𝑓(𝑥) =
    (re.compile(r'([a-záàâãéêíóôõúç])([𝑓𝑔]\([^)]+\)\s*=)', re.IGNORECASE), r'\1 \2'),
    # )texto -> ) texto (após fechar parêntese de fórmula)
    (re.compile(r'(\))(responda|determine|calcule|qual|onde|sendo|para|com)', re.IGNORECASE), r'\1 \2'),
    # número)letra -> número) letra
    (re.compile(r'(\d\))([a-záàâãéêíóôõúç])', re.IGNORECASE), r'\1 \2'),
    # a)𝑓(1) ou b)𝑓(x) -> a) 𝑓(1) ou b) 𝑓(x) (letra seguida de ) e símbolo math)
    (re.compile(r'([a-z]\))([𝑓𝑔𝑥𝑦𝑧𝑎𝑏𝑐𝑛𝑚𝑘ƒ])', re.IGNORECASE), r'\1 \2'),
    # )= -> ) = (espaço antes de igual após parêntese)
    (re.compile(r'\)='), r') ='),
    # =? -> = ? (espaço antes de interrogação)
    (re.compile(r'=\?'), r'= ?'),
]


def add_math_symbol_spacing(text: str) -> str:
    """
    Adiciona espaçamento adequado ao redor de símbolos matemáticos.

    Resolve problemas como:
    - "função𝑓(𝑥)" -> "função 𝑓(𝑥)"
    - "b)𝑓(1)" -> "b) 𝑓(1)"

    Args:
        text: Texto a processar

    Returns:
        Texto com espaçamento corrigido
    """
    if not text:
        return text

    result = text

    # Aplicar padrões de espaçamento
    for pattern, replacement in INLINE_FORMULA_PATTERNS:
        result = pattern.sub(replacement, result)

    # Espaçamento genérico: letra minúscula seguida de símbolo math Unicode
    # Cuidado para não quebrar palavras normais
    for symbol in MATH_FUNCTION_SYMBOLS:
        # palavra + símbolo math -> palavra + espaço + símbolo
        pattern = re.compile(f'([a-záàâãéêíóôõúç])({re.escape(symbol)})', re.IGNORECASE)
        result = pattern.sub(r'\1 \2', result)

    # Limpar espaços duplos que possam ter sido criados
    result = re.sub(r'  +', ' ', result)

    return result


def detect_inline_formula(text: str) -> bool:
    """
    Detecta se uma linha contém fórmulas inline (grudadas no texto).

    Args:
        text: Texto a verificar

    Returns:
        True se contém fórmula inline
    """
    if not text:
        return False

    # Verificar símbolos matemáticos Unicode
    math_chars = set('𝑓𝑔𝑥𝑦𝑧𝑎𝑏𝑐𝑛𝑚𝑘𝐴𝐵𝐶√∫∑∏')
    if any(c in text for c in math_chars):
        return True

    # Verificar padrões de função
    if re.search(r'[𝑓𝑔ƒ]\s*\([^)]+\)', text):
        return True

    # Verificar letras gregas
    greek = set('αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ')
    if any(c in text for c in greek):
        return True

    return False


# Mapeamento de modelos por RAM disponível
MODEL_BY_RAM: Dict[float, Tuple[str, str]] = {
    # RAM_GB: (model_id, model_name_friendly)
    1.0: ("Qwen/Qwen2.5-0.5B-Instruct", "Qwen2.5-0.5B"),
    2.0: ("Qwen/Qwen2.5-0.5B-Instruct", "Qwen2.5-0.5B"),
    3.0: ("Qwen/Qwen2.5-1.5B-Instruct", "Qwen2.5-1.5B"),
    4.0: ("Qwen/Qwen2.5-1.5B-Instruct", "Qwen2.5-1.5B"),
    6.0: ("Qwen/Qwen2.5-3B-Instruct", "Qwen2.5-3B"),
    8.0: ("Qwen/Qwen2.5-3B-Instruct", "Qwen2.5-3B"),
    12.0: ("Qwen/Qwen2.5-7B-Instruct", "Qwen2.5-7B"),
}


def select_model_for_ram(ram_gb: float) -> Tuple[str, str]:
    """Seleciona o melhor modelo para a RAM disponível."""
    # Encontrar o maior modelo que cabe na RAM
    selected = None
    for ram_threshold in sorted(MODEL_BY_RAM.keys()):
        if ram_threshold <= ram_gb:
            selected = MODEL_BY_RAM[ram_threshold]

    if selected is None:
        # Fallback para o menor modelo
        selected = MODEL_BY_RAM[1.0]

    return selected


# Prompt do sistema para conversão de fórmulas
SYSTEM_PROMPT = """You are a mathematical formula converter. Your task is to identify mathematical formulas in text and convert them to proper LaTeX format.

Rules:
1. Only convert actual mathematical expressions, NOT regular text
2. Wrap inline math with single $ signs: $formula$
3. Keep display/block math with $$ signs: $$formula$$
4. Preserve all parentheses and structure
5. Convert Greek letters: ρ→\\rho, γ→\\gamma, α→\\alpha, β→\\beta, μ→\\mu, etc.
6. Convert fractions like a/b to \\frac{a}{b} only when it's clearly a math fraction
7. Convert superscripts: x² → x^{2}, m³ → m^{3}
8. Convert subscripts: x₁ → x_{1}, H₂O → H_2O
9. DO NOT modify text that is not mathematical
10. If a line has no math, return it unchanged
11. Be conservative - when in doubt, don't convert

Examples:
Input: "O valor de ρ = m/V representa a densidade"
Output: "O valor de $\\rho = \\frac{m}{V}$ representa a densidade"

Input: "Este é um texto normal sem matemática"
Output: "Este é um texto normal sem matemática"

Input: "A equação γ = ρg relaciona peso e massa específica"
Output: "A equação $\\gamma = \\rho g$ relaciona peso e massa específica"

Input: "Água: γ = 1000 kgf/m³"
Output: "Água: $\\gamma = 1000$ kgf/m³"

Input: "A fórmula PV = nRT é dos gases ideais"
Output: "A fórmula $PV = nRT$ é dos gases ideais"

Input: "Para x² + y² = r² temos um círculo"
Output: "Para $x^{2} + y^{2} = r^{2}$ temos um círculo"

Now convert the following text. Return ONLY the converted text, nothing else:"""


class LLMFormulaConverter:
    """
    Conversor de fórmulas usando LLM local.

    Usa modelos pequenos para converter fórmulas matemáticas
    de texto PDF para LaTeX, respeitando limites de RAM.
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Inicializa o conversor.

        Args:
            config: Configuração opcional
        """
        self.config = config or LLMConfig()
        self._model = None
        self._tokenizer = None
        self._pipeline = None
        self._loaded = False
        self._cache: Dict[str, str] = {}
        self._stats = {
            'lines_processed': 0,
            'lines_converted': 0,
            'cache_hits': 0,
            'errors': 0,
        }

        # Selecionar modelo baseado em RAM
        if self.config.model_name:
            self._model_id = self.config.model_name
            self._model_name = self.config.model_name.split('/')[-1]
        else:
            self._model_id, self._model_name = select_model_for_ram(
                self.config.ram_limit_gb
            )

    def _check_dependencies(self) -> bool:
        """Verifica se as dependências estão instaladas."""
        try:
            import torch
            import transformers
            return True
        except ImportError:
            return False

    def _load_model(self) -> bool:
        """Carrega o modelo LLM."""
        if self._loaded:
            return True

        if not self._check_dependencies():
            logger.warning(
                "Dependências não instaladas. Instale com: "
                "pip install torch transformers accelerate"
            )
            return False

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

            logger.info(f"Carregando modelo {self._model_name}...")
            print(f"   🔄 Carregando modelo {self._model_name}...")

            # Determinar device - PRIORIZA GPU
            if self.config.device == "auto":
                if torch.cuda.is_available() and self.config.prefer_gpu:
                    device = "cuda"
                    # Configurar fração de memória GPU
                    if self.config.gpu_memory_fraction < 1.0:
                        torch.cuda.set_per_process_memory_fraction(
                            self.config.gpu_memory_fraction
                        )
                    logger.info(f"Usando GPU: {torch.cuda.get_device_name(0)}")
                    print(f"   🎮 GPU detectada: {torch.cuda.get_device_name(0)}")
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    device = "mps"
                    print(f"   🍎 Usando Apple Metal (MPS)")
                else:
                    device = "cpu"
                    print(f"   💻 Usando CPU (mais lento)")
            else:
                device = self.config.device

            # Configurar quantização se disponível e habilitada
            model_kwargs = {"trust_remote_code": True}

            if self.config.use_quantization and device == "cuda":
                try:
                    from transformers import BitsAndBytesConfig
                    # Quantização 4-bit para usar menos VRAM
                    model_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_use_double_quant=True,  # Quantização dupla para economia extra
                    )
                    print(f"   ⚡ Quantização 4-bit habilitada")
                except ImportError:
                    logger.warning("bitsandbytes não instalado, usando precisão total")
                    print(f"   ⚠️ bitsandbytes não instalado, usando float16")
                    model_kwargs["torch_dtype"] = torch.float16
            elif device == "cuda":
                # GPU sem quantização - usar float16
                model_kwargs["torch_dtype"] = torch.float16
            else:
                # CPU - usar float32
                model_kwargs["torch_dtype"] = torch.float32

            # Carregar tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_id,
                trust_remote_code=True
            )

            # Carregar modelo
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_id,
                device_map="auto" if device == "cuda" else None,
                **model_kwargs
            )

            if device != "cuda":
                self._model = self._model.to(device)

            # Criar pipeline
            self._pipeline = pipeline(
                "text-generation",
                model=self._model,
                tokenizer=self._tokenizer,
                device=None if device == "cuda" else device,
            )

            self._loaded = True
            logger.info(f"Modelo {self._model_name} carregado com sucesso")
            print(f"   ✓ Modelo carregado ({device})")

            return True

        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            print(f"   ⚠️ Erro ao carregar modelo: {e}")
            return False

    def _convert_line_with_llm(self, line: str) -> str:
        """Converte uma linha usando o LLM."""
        if not line.strip():
            return line

        # Verificar cache
        if self.config.use_cache and line in self._cache:
            self._stats['cache_hits'] += 1
            return self._cache[line]

        try:
            # Preparar prompt
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": line}
            ]

            # Gerar resposta
            result = self._pipeline(
                messages,
                max_new_tokens=len(line) * 2 + 50,
                do_sample=False,
                temperature=0.1,
                return_full_text=False,
            )

            if result and len(result) > 0:
                converted = result[0]['generated_text'].strip()

                # Limpar possíveis artefatos
                converted = self._clean_output(converted, line)

                # Cachear
                if self.config.use_cache:
                    if len(self._cache) >= self.config.cache_size:
                        # Limpar metade do cache (FIFO simples)
                        keys = list(self._cache.keys())[:len(self._cache)//2]
                        for k in keys:
                            del self._cache[k]
                    self._cache[line] = converted

                return converted

            return line

        except Exception as e:
            logger.warning(f"Erro ao converter linha: {e}")
            self._stats['errors'] += 1
            return line if self.config.fallback_to_original else line

    def _clean_output(self, output: str, original: str) -> str:
        """Limpa a saída do LLM."""
        # Remover possíveis prefixos/sufixos indesejados
        output = output.strip()

        # Se a saída ficou muito diferente em tamanho, pode ser erro
        if len(output) > len(original) * 3:
            return original

        if len(output) < len(original) * 0.3:
            return original

        # Remover possíveis marcadores de código
        if output.startswith("```"):
            lines = output.split('\n')
            if len(lines) > 2:
                output = '\n'.join(lines[1:-1])

        return output

    def convert_line(self, line: str) -> str:
        """
        Converte uma única linha.

        Primeiro aplica espaçamento de símbolos matemáticos,
        depois usa LLM se necessário.

        Args:
            line: Linha a converter

        Returns:
            Linha convertida (ou original se não houver matemática)
        """
        self._stats['lines_processed'] += 1

        # Pular linhas vazias ou muito curtas
        if not line.strip() or len(line.strip()) < 3:
            return line

        # PRIMEIRO: aplicar espaçamento de símbolos matemáticos inline
        # Isso resolve casos como "função𝑓(𝑥)" -> "função 𝑓(𝑥)"
        line = add_math_symbol_spacing(line)

        # Verificar se tem potencial matemático (otimização)
        if not self._has_potential_math(line):
            return line

        # Carregar modelo se necessário
        if not self._loaded:
            if not self._load_model():
                return line  # Fallback: retornar original

        # Converter com LLM
        converted = self._convert_line_with_llm(line)

        if converted != line:
            self._stats['lines_converted'] += 1

        return converted

    def _has_potential_math(self, text: str) -> bool:
        """Verifica rapidamente se texto pode ter matemática."""
        # Caracteres que indicam matemática
        math_indicators = set('αβγδεζηθικλμνξοπρστυφχψωΓΔΘΛΞΠΣΦΨΩ')
        math_indicators.update('∞∑∫∂√≤≥≠≈∈±×÷·²³⁴⁵⁶⁷⁸⁹⁰¹₀₁₂₃₄₅₆₇₈₉')
        # Adicionar símbolos matemáticos Unicode
        math_indicators.update('𝑓𝑔𝑥𝑦𝑧𝑎𝑏𝑐𝑛𝑚𝑘𝐴𝐵𝐶')

        # Verificar caracteres
        if any(c in text for c in math_indicators):
            return True

        # Verificar padrões simples
        if re.search(r'[a-zA-Z]\s*=\s*[a-zA-Z0-9]', text):
            return True

        if re.search(r'\d+/\d+', text):
            return True

        # Verificar fórmulas inline (função seguida de parênteses)
        if detect_inline_formula(text):
            return True

        return False

    def convert_text(self, text: str) -> str:
        """
        Converte texto completo (múltiplas linhas).

        Args:
            text: Texto a converter

        Returns:
            Texto com fórmulas convertidas para LaTeX
        """
        if not text:
            return text

        lines = text.split('\n')
        converted_lines = []

        for line in lines:
            converted_lines.append(self.convert_line(line))

        return '\n'.join(converted_lines)

    def convert_batch(self, lines: List[str]) -> List[str]:
        """
        Converte um lote de linhas.

        Args:
            lines: Lista de linhas

        Returns:
            Lista de linhas convertidas
        """
        return [self.convert_line(line) for line in lines]

    def is_available(self) -> bool:
        """Verifica se o conversor LLM está disponível."""
        return self._check_dependencies()

    def get_model_info(self) -> Dict:
        """Retorna informações sobre o modelo."""
        return {
            'model_id': self._model_id,
            'model_name': self._model_name,
            'ram_limit_gb': self.config.ram_limit_gb,
            'loaded': self._loaded,
            'available': self.is_available(),
        }

    def get_stats(self) -> Dict:
        """Retorna estatísticas de uso."""
        return self._stats.copy()

    def reset_stats(self):
        """Reseta estatísticas."""
        self._stats = {
            'lines_processed': 0,
            'lines_converted': 0,
            'cache_hits': 0,
            'errors': 0,
        }

    def unload_model(self):
        """Descarrega o modelo para liberar memória."""
        if self._loaded:
            del self._model
            del self._tokenizer
            del self._pipeline
            self._model = None
            self._tokenizer = None
            self._pipeline = None
            self._loaded = False

            # Forçar coleta de lixo
            import gc
            gc.collect()

            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except:
                pass

            logger.info("Modelo descarregado")


# =============================================================================
# FALLBACK SEM LLM - Conversões básicas seguras
# =============================================================================

class SimpleFallbackConverter:
    """
    Conversor simples sem LLM.

    Faz apenas conversões seguras que não quebram o texto:
    - Superscripts/subscripts Unicode → LaTeX
    - Espaçamento de símbolos matemáticos
    """

    def __init__(self):
        self._stats = {
            'lines_processed': 0,
            'chars_converted': 0,
        }

        # Mapeamento de superscripts Unicode
        self._superscripts = {
            '⁰': '^{0}', '¹': '^{1}', '²': '^{2}', '³': '^{3}',
            '⁴': '^{4}', '⁵': '^{5}', '⁶': '^{6}', '⁷': '^{7}',
            '⁸': '^{8}', '⁹': '^{9}', '⁺': '^{+}', '⁻': '^{-}',
            'ⁿ': '^{n}', 'ⁱ': '^{i}',
        }

        # Mapeamento de subscripts Unicode
        self._subscripts = {
            '₀': '_{0}', '₁': '_{1}', '₂': '_{2}', '₃': '_{3}',
            '₄': '_{4}', '₅': '_{5}', '₆': '_{6}', '₇': '_{7}',
            '₈': '_{8}', '₉': '_{9}', '₊': '_{+}', '₋': '_{-}',
            'ₙ': '_{n}', 'ₘ': '_{m}', 'ₐ': '_{a}', 'ₑ': '_{e}',
            'ₒ': '_{o}', 'ₓ': '_{x}', 'ₕ': '_{h}', 'ₖ': '_{k}',
            'ₗ': '_{l}', 'ₚ': '_{p}', 'ₛ': '_{s}', 'ₜ': '_{t}',
        }

    def convert_line(self, line: str) -> str:
        """Converte uma linha com fallback seguro."""
        if not line:
            return line

        self._stats['lines_processed'] += 1

        # PRIMEIRO: aplicar espaçamento de símbolos matemáticos
        result = add_math_symbol_spacing(line)

        # Converter superscripts
        for char, latex in self._superscripts.items():
            if char in result:
                result = result.replace(char, latex)
                self._stats['chars_converted'] += 1

        # Converter subscripts
        for char, latex in self._subscripts.items():
            if char in result:
                result = result.replace(char, latex)
                self._stats['chars_converted'] += 1

        return result

    def convert_text(self, text: str) -> str:
        """Converte texto completo."""
        if not text:
            return text

        lines = text.split('\n')
        return '\n'.join(self.convert_line(line) for line in lines)

    def get_stats(self) -> dict:
        """Retorna estatísticas."""
        return self._stats.copy()


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================

class SimpleFallbackConverter:
    """
    Conversor simples de fallback quando LLM não está disponível.

    Faz apenas conversões muito seguras e conservadoras.
    """

    # Mapeamento de letras gregas
    GREEK_MAP = {
        'α': '\\alpha', 'β': '\\beta', 'γ': '\\gamma', 'δ': '\\delta',
        'ε': '\\varepsilon', 'ζ': '\\zeta', 'η': '\\eta', 'θ': '\\theta',
        'ι': '\\iota', 'κ': '\\kappa', 'λ': '\\lambda', 'μ': '\\mu',
        'ν': '\\nu', 'ξ': '\\xi', 'π': '\\pi', 'ρ': '\\rho',
        'σ': '\\sigma', 'τ': '\\tau', 'υ': '\\upsilon', 'φ': '\\varphi',
        'χ': '\\chi', 'ψ': '\\psi', 'ω': '\\omega',
        'Γ': '\\Gamma', 'Δ': '\\Delta', 'Θ': '\\Theta', 'Λ': '\\Lambda',
        'Ξ': '\\Xi', 'Π': '\\Pi', 'Σ': '\\Sigma', 'Φ': '\\Phi',
        'Ψ': '\\Psi', 'Ω': '\\Omega',
    }

    # Superscripts
    SUPERSCRIPT_MAP = {
        '²': '^{2}', '³': '^{3}', '⁴': '^{4}', '⁵': '^{5}',
        '⁶': '^{6}', '⁷': '^{7}', '⁸': '^{8}', '⁹': '^{9}',
        '⁰': '^{0}', '¹': '^{1}', 'ⁿ': '^{n}',
    }

    # Subscripts
    SUBSCRIPT_MAP = {
        '₀': '_{0}', '₁': '_{1}', '₂': '_{2}', '₃': '_{3}',
        '₄': '_{4}', '₅': '_{5}', '₆': '_{6}', '₇': '_{7}',
        '₈': '_{8}', '₉': '_{9}', 'ₙ': '_{n}',
    }

    def __init__(self):
        self._stats = {'lines_processed': 0, 'chars_converted': 0}

    def convert_line(self, line: str) -> str:
        """Converte linha com substituições seguras apenas."""
        self._stats['lines_processed'] += 1

        if not line.strip():
            return line

        result = line

        # Converter superscripts (muito seguro)
        for uni, latex in self.SUPERSCRIPT_MAP.items():
            if uni in result:
                result = result.replace(uni, latex)
                self._stats['chars_converted'] += 1

        # Converter subscripts (muito seguro)
        for uni, latex in self.SUBSCRIPT_MAP.items():
            if uni in result:
                result = result.replace(uni, latex)
                self._stats['chars_converted'] += 1

        # NÃO converter letras gregas automaticamente
        # pois precisam de contexto ($...$) para funcionar

        return result

    def convert_text(self, text: str) -> str:
        """Converte texto completo."""
        if not text:
            return text

        lines = text.split('\n')
        return '\n'.join(self.convert_line(line) for line in lines)

    def get_stats(self) -> Dict:
        return self._stats.copy()


# =============================================================================
# FUNÇÕES UTILITÁRIAS
# =============================================================================

def get_formula_converter(
    ram_limit_gb: float = RAM_LIMIT_GB,
    use_llm: bool = True
) -> 'LLMFormulaConverter | SimpleFallbackConverter':
    """
    Obtém o conversor apropriado.

    Args:
        ram_limit_gb: Limite de RAM em GB
        use_llm: Se deve tentar usar LLM

    Returns:
        Conversor (LLM se disponível, senão fallback)
    """
    if use_llm:
        config = LLMConfig(ram_limit_gb=ram_limit_gb)
        converter = LLMFormulaConverter(config)

        if converter.is_available():
            return converter

    logger.info("Usando conversor fallback (sem LLM)")
    return SimpleFallbackConverter()


def convert_formulas_with_llm(
    text: str,
    ram_limit_gb: float = RAM_LIMIT_GB
) -> str:
    """
    Converte fórmulas em texto usando LLM.

    Args:
        text: Texto a converter
        ram_limit_gb: Limite de RAM em GB

    Returns:
        Texto com fórmulas convertidas
    """
    converter = get_formula_converter(ram_limit_gb)
    return converter.convert_text(text)


def check_llm_available() -> Tuple[bool, str]:
    """
    Verifica se LLM está disponível (API externa ou local).

    Returns:
        Tupla (disponível, mensagem)
    """
    # Carregar variáveis de ambiente primeiro
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Primeiro, verificar se API externa está configurada
    try:
        from app.utils.api_formula_converter import get_api_converter
        api_converter = get_api_converter()
        if api_converter.is_available():
            return True, f"LLM disponível via API ({api_converter.config.provider.value}: {api_converter.config.model})"
    except ImportError:
        pass

    # Fallback: verificar LLM local
    try:
        import torch
        import transformers

        # Verificar GPU
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            return True, f"LLM disponível (GPU: {gpu_name}, {gpu_mem:.1f}GB)"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return True, "LLM disponível (Apple Silicon MPS)"
        else:
            return True, "LLM disponível (CPU only - será mais lento)"

    except ImportError as e:
        return False, f"LLM não disponível: API não configurada e dependências locais não instaladas ({e})"


def get_recommended_model(ram_gb: float) -> str:
    """
    Retorna o modelo recomendado para a RAM disponível.

    Args:
        ram_gb: RAM disponível em GB

    Returns:
        Nome do modelo recomendado
    """
    _, model_name = select_model_for_ram(ram_gb)
    return model_name


# Expor configuração de RAM para fácil ajuste
def set_ram_limit(gb: float):
    """
    Define o limite de RAM globalmente.

    Args:
        gb: Limite em GB
    """
    global RAM_LIMIT_GB
    RAM_LIMIT_GB = gb


def get_ram_limit() -> float:
    """Retorna o limite de RAM atual."""
    return RAM_LIMIT_GB
