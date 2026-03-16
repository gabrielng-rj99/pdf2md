"""
Conversor de fórmulas usando APIs LLM externas.

Suporta múltiplos provedores:
- OpenAI (GPT-4, GPT-4o, GPT-4o-mini)
- Anthropic (Claude)
- Google (Gemini)
- Ollama (local)

Usage:
    converter = APIFormulaConverter()
    latex = converter.convert("A fórmula f(x) = x² + 1")

    # Batch conversion
    responses = converter.convert_batch([
        FormulaRequest(id="1", original_text="x^2 + y^2", page_num=1),
        FormulaRequest(id="2", original_text="\\int_0^1 x dx", page_num=1),
    ])
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

import requests

logger = logging.getLogger(__name__)


class Provider(Enum):
    """Provedores LLM suportados."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    CUSTOM = "custom"


@dataclass
class APIConfig:
    """Configuração da API LLM."""
    provider: Provider = Provider.OPENAI
    api_key: str = ""
    api_url: str = ""
    model: str = "gpt-4o-mini"
    timeout: int = 60  # Aumentado de 30 para 60 segundos
    max_tokens: int = 2048
    temperature: float = 0.1

    # Batch settings
    batch_size: int = 5  # Reduzido para evitar timeouts
    max_retries: int = 3
    retry_delay: float = 2.0  # Segundos entre retries

    # Chunking settings - máximo de chamadas API por arquivo
    max_api_calls_per_file: int = 10  # Limite de chamadas por arquivo
    formulas_per_call: int = 10  # Fórmulas por chamada (chunk size)

    # Fallback
    fallback_to_images: bool = True


@dataclass
class FormulaRequest:
    """Requisição de conversão de fórmula."""
    id: str                      # ID único
    original_text: str           # Texto original (ou descrição da imagem)
    page_num: int                # Página de origem
    bbox: Optional[Tuple] = None # Posição no PDF (opcional)
    is_image: bool = False      # Se é uma imagem


@dataclass
class FormulaResponse:
    """Resposta da conversão de fórmula."""
    id: str
    original: str
    latex: str
    confidence: float
    success: bool
    error: Optional[str] = None


# Prompt do sistema para conversão de fórmulas
FORMULA_SYSTEM_PROMPT = """You are an expert at converting mathematical formulas to LaTeX.

Your task is to:
1. Identify mathematical expressions in text or describe images
2. Convert them to proper LaTeX format
3. Return ONLY valid LaTeX, no explanations

Rules:
- Inline math: wrap with $...$
- Block math: wrap with $$...$$
- Use proper LaTeX commands: \\frac{}{}, \\sqrt{}, \\sum{}, \\int{}, etc.
- Greek letters: \\alpha, \\beta, \\gamma, etc.
- For images: describe what you see in the image mathematically

Return format (JSON):
{"latex": "the_latex_formula", "confidence": 0.95}

If the input is not mathematical, return:
{"latex": "original_text", "confidence": 0.0}"""


FORMULA_USER_PROMPT = """Convert this mathematical formula to LaTeX:

{formula}

Return JSON only."""

CONTEXT_SYSTEM_PROMPT = r"""You are an expert mathematical formatter specializing in LaTeX.
Your task is to convert mathematical formulas to proper LaTeX format.

CRITICAL RULES:
1. Use $...$ for inline formulas (e.g., $x^2 + y^2$).
2. Use $$...$$ ONLY for formulas that should be on their own line (display math).
3. Recognize common formulas by context:
   - Bhaskara/quadratic: $x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}$
   - Density: $\rho = \frac{m}{V}$ or $\rho = m/V$
   - Specific weight: $\gamma = \rho g$
   - Ideal gas: $PV = nRT$
   - Pressure: $P = \frac{F}{A}$
   - Stevin's law: $P = P_0 + \rho g h$
4. Convert ALL Greek letters: ρ→\rho, γ→\gamma, α→\alpha, β→\beta, Δ→\Delta, μ→\mu, etc.
5. Convert fractions: a/b → \frac{a}{b} when it's a math fraction.
6. Convert superscripts: x² → x^{2}, x³ → x^{3}.
7. Convert subscripts: x₁ → x_{1}, x₀ → x_{0}.
8. Convert functions: sen→\sin, cos→\cos, tan→\tan, log→\log, ln→\ln.
9. Keep the formula structure mathematically correct.
10. Return ONLY the LaTeX formula, no explanations."""

CONTEXT_USER_PROMPT = """Convert this mathematical formula to LaTeX.
Use the context to understand what formula this represents if it's unclear.

Context before: {context_before}
Formula to convert: {formula}
Context after: {context_after}

Return ONLY the LaTeX formula wrapped in $...$ for inline or $$...$$ for display."""

# Prompt para múltiplos snippets sem contexto individual
BATCH_FORMULA_PROMPT = """Fix the mathematical formulas in these text snippets. Return the results in the same order, one per line:

{formula_snippets}"""


class APIFormulaConverter:
    """
    Conversor de fórmulas usando APIs LLM externas.

    Suporta batch processing para eficiência.
    """

    def __init__(self, config: Optional[APIConfig] = None):
        """
        Inicializa o conversor.

        Args:
            config: Configuração da API. Se None, carrega do ambiente.
        """
        self.config = config or self._load_config_from_env()
        self._session = requests.Session()
        self._stats = {
            'requests': 0,
            'success': 0,
            'errors': 0,
        }

    def _load_config_from_env(self) -> APIConfig:
        """Carrega configuração do ambiente."""
        # Determinar provedor
        provider_name = os.getenv('LLM_PROVIDER', 'openai').lower()

        try:
            provider = Provider(provider_name)
        except ValueError:
            logger.warning(f"Unknown provider {provider_name}, using openai")
            provider = Provider.OPENAI

        # Obter API key
        api_key = os.getenv('LLM_API_KEY', '')
        if not api_key:
            logger.warning("LLM_API_KEY not set, API conversion will not work")

        # Obter API URL ou usar padrão
        api_url = os.getenv('LLM_API_URL', '')

        # Obter modelo
        model = os.getenv('LLM_MODEL', 'gpt-4o-mini')

        return APIConfig(
            provider=provider,
            api_key=api_key,
            api_url=api_url,
            model=model,
            timeout=int(os.getenv('LLM_TIMEOUT', '30')),
            max_tokens=int(os.getenv('LLM_MAX_TOKENS', '2048')),
            temperature=float(os.getenv('LLM_TEMPERATURE', '0.1')),
            batch_size=int(os.getenv('FORMULA_BATCH_SIZE', '10')),
            max_retries=int(os.getenv('FORMULA_MAX_RETRIES', '3')),
            max_api_calls_per_file=int(os.getenv('FORMULA_MAX_CALLS_PER_FILE', '10')),
            formulas_per_call=int(os.getenv('FORMULA_FORMULAS_PER_CALL', '10')),
            fallback_to_images=os.getenv('FALLBACK_TO_IMAGES', 'true').lower() == 'true'
        )

    def is_available(self) -> bool:
        """Verifica se API está disponível."""
        return bool(self.config.api_key)

    def convert(self, formula: str) -> FormulaResponse:
        """
        Converte uma única fórmula.

        Args:
            formula: Texto ou descrição da fórmula

        Returns:
            FormulaResponse com resultado
        """
        self._stats['requests'] += 1

        if not self.is_available():
            return FormulaResponse(
                id="1",
                original=formula,
                latex=formula,
                confidence=0.0,
                success=False,
                error="API key not configured"
            )

        # Construir prompt
        user_prompt = FORMULA_USER_PROMPT.format(formula=formula)

        try:
            response = self._make_request(
                system_prompt=FORMULA_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )

            # Parsear resposta
            result = self._parse_response(response)

            self._stats['success'] += 1
            return FormulaResponse(
                id="1",
                original=formula,
                latex=result.get('latex', formula),
                confidence=result.get('confidence', 0.5),
                success=True
            )

        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"Erro ao converter fórmula: {e}")
            return FormulaResponse(
                id="1",
                original=formula,
                latex=formula,
                confidence=0.0,
                success=False,
                error=str(e)
            )

    def _extract_formula_snippets(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Extrai apenas os trechos que parecem ser fórmulas matemáticas.
        
        Returns:
            Lista de tuplas (snippet, start_pos, end_pos)
        """
        import re
        snippets = []
        
        # Padrões de fórmulas matemáticas
        patterns = [
            # Caracteres Unicode privados (PDFs com fontes customizadas)
            (r'[\uf000-\uf0ff][\s]*[:=＝;]?', 0.9),
            # Letras gregas isoladas com contexto matemático
            (r'[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ][\s]*[=＝][\s]*[^\s]{1,20}', 0.9),
            # Variável = expressão (fórmula simples)
            (r'\b[xyzwabcαβγδρλμσθ\uf000-\uf0ff][\s]*[=＝][\s]*[^.,;]{1,30}', 0.8),
            # Expressões com frações como a/b
            (r'\b\w+[\s]*/[\s]*\w+[\s]*(?:[=＝][\s]*[^.,;]{0,20})?', 0.8),
            # Expressões com parênteses e operadores
            (r'\([^)]{3,50}\)[\s]*[=＝][\s]*[^.,;]{1,20}', 0.7),
            # Sequências de variáveis e operadores
            (r'[xyzwabc][\s]*[\+\-\*/][\s]*[xyzwabc][\s]*[\+\-\*/]?[\s]*[xyzwabc0-9]*', 0.6),
            # Padrões tipo f(x) = ...
            (r'[ƒ𝑓f][\s]*\([^)]+\)[\s]*[=＝][^.,;]{1,30}', 0.9),
            # Números com unidades (pode ser fórmula aplicada)
            (r'\d+[\s]*[a-zA-Z/²³]+[\s]*[=＝][\s]*\d', 0.5),
            # Bhaskara e fórmulas similares
            (r'[\-–−]?[\s]*[bβ][\s]*[±\+\-][\s]*√[\s]*[Δb]', 0.95),
            # Raiz quadrada em texto
            (r'√[\s]*\(?[\s]*[a-zA-Z0-9\s\+\-²³²³]{1,20}\)?', 0.8),
            # Delta b² - 4ac
            (r'[ΔΔ][\s]*[=＝]?[\s]*[bβ]?[\s]*²?[\s]*[\-–−]?[\s]*4[\s]*[aα][\s]*[cγ]', 0.9),
            # Letras gregas ISOLADAS em contextos de definição (ex: "massa específica ρ:")
            # Captura a palavra antes + a letra grega
            (r'(?:massa|peso|densidade|volume|pressão|viscosidade|tensão|ângulo|temperatura)[\s]+(?:específica|específico)?[\s]*[αβγδεζηθικλμνξοπρστυφχψω][\s]*[:;)]', 0.85),
            # Letras gregas seguidas de dois pontos ou ponto e vírgula
            (r'\b[αβγδεζηθικλμνξοπρστυφχψω][\s]*[:;]', 0.7),
        ]
        
        # Conjunto para evitar overlaps
        covered = set()
        
        for pattern, confidence in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start, end = match.span()
                # Verificar se já foi coberto
                if any(i in covered for i in range(start, end)):
                    continue
                snippet = match.group().strip()
                # Filtrar snippets muito curtos ou muito longos
                # Mínimo 2 caracteres para capturar símbolos Unicode privados + pontuação (ex: \uf072:)
                if len(snippet) >= 2 and len(snippet) <= 100:
                    snippets.append((snippet, start, end, confidence))
                    for i in range(start, end):
                        covered.add(i)
        
        # Ordenar por posição
        snippets.sort(key=lambda x: x[1])
        return [(s, start, end) for s, start, end, _ in snippets]

    def fix_paragraph(self, text: str, context_before: str = "", context_after: str = "") -> str:
        """
        Fixes mathematical formula snippets in text using LLM.
        
        Uses context (text before and after) to better understand what formula
        is being represented, especially for fragmented formulas.
        
        Args:
            text: The text containing formulas to fix
            context_before: Text that comes before this paragraph (for context)
            context_after: Text that comes after this paragraph (for context)
        
        Returns:
            Text with formulas converted to LaTeX
        """
        import time
        import re
        
        if not self.is_available():
            return text
        
        # Extrair apenas snippets de fórmulas
        snippets = self._extract_formula_snippets(text)
        
        # Se não há fórmulas, retornar texto original
        if not snippets:
            return text
        
        # Processar com contexto
        return self._fix_formula_with_context(text, snippets, context_before, context_after)

    def _fix_formula_with_context(
        self, 
        original_text: str, 
        snippets: List[Tuple[str, int, int]],
        context_before: str = "",
        context_after: str = ""
    ) -> str:
        """
        Processa snippets de fórmulas com contexto e substitui no texto original.
        
        Args:
            original_text: Texto original
            snippets: Lista de (snippet, start, end)
            context_before: Contexto anterior ao texto
            context_after: Contexto posterior ao texto
        """
        import time
        
        if not snippets:
            return original_text
        
        # Limitar contexto para não sobrecarregar
        context_before = context_before[-200:] if len(context_before) > 200 else context_before
        context_after = context_after[:200] if len(context_after) > 200 else context_after
        
        result = original_text
        total_snippets = len(snippets)
        
        # Processar cada snippet individualmente com contexto
        # (fazemos de trás para frente para não deslocar posições)
        for i, (snippet, start, end) in enumerate(reversed(snippets)):
            snippet_num = total_snippets - i
            self._stats['requests'] += 1
            
            # Log do progresso
            print(f"         🧮 Fórmula {snippet_num}/{total_snippets}: '{snippet[:40]}...'", end=" ", flush=True)
            
            # Preparar contexto específico para este snippet
            # Pegar um pouco do texto ao redor do snippet como contexto local
            local_before = original_text[max(0, start-30):start]
            local_after = original_text[end:min(len(original_text), end+30)]
            
            # Combinar contextos
            full_context_before = f"{context_before} {local_before}".strip()
            full_context_after = f"{local_after} {context_after}".strip()
            
            user_prompt = CONTEXT_USER_PROMPT.format(
                context_before=full_context_before if full_context_before else "(none)",
                formula=snippet,
                context_after=full_context_after if full_context_after else "(none)"
            )
            
            # Tentar com retries (timeout curto por snippet)
            last_error = None
            fixed = None
            start_time = time.time()
            
            # Timeout curto para cada snippet (15s)
            snippet_timeout = min(15, self.config.timeout)
            
            for attempt in range(self.config.max_retries):
                try:
                    # Criar uma sessão temporária com timeout curto
                    import requests
                    temp_session = requests.Session()
                    
                    response = self._make_request_with_timeout(
                        system_prompt=CONTEXT_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        timeout=snippet_timeout,
                        session=temp_session
                    )
                    
                    response = response.strip()
                    
                    # Remover blocos <think>...</think> (resposta do MiniMax/DeepSeek)
                    import re
                    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
                    
                    # Remover blocos de código markdown
                    if response.startswith("```"):
                        lines = response.split('\n')
                        if lines[0].startswith("```"):
                           lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                           lines = lines[:-1]
                        response = '\n'.join(lines)
                    
                    fixed = response.strip()
                    self._stats['success'] += 1
                    elapsed = time.time() - start_time
                    print(f"✓ ({elapsed:.1f}s)")
                    break
                    
                except Exception as e:
                    last_error = e
                    self._stats['errors'] += 1
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay)
                    else:
                        elapsed = time.time() - start_time
                        print(f"✗ ({elapsed:.1f}s) - {str(e)[:40]}")
            
            # Se conseguiu converter, substituir
            if fixed and fixed != snippet and not fixed.startswith("Erro"):
                # Ajustar posições porque o texto está mudando
                offset = len(result) - len(original_text)
                adjusted_start = start + offset
                adjusted_end = end + offset
                result = result[:adjusted_start] + fixed + result[adjusted_end:]
        
        return result

    def fix_paragraphs_batch(
        self,
        text: str,
        context_before: str = "",
        context_after: str = ""
    ) -> Tuple[str, int]:
        """
        Processa TODAS as fórmulas de um texto em batch com chunking.

        Otimizado para:
        - Uma única chamada API por chunk (em vez de uma por fórmula)
        - Chunking automático baseado em formulas_per_call
        - Máximo de chamadas definido por max_api_calls_per_file

        Args:
            text: Texto com fórmulas para corrigir
            context_before: Texto antes do parágrafo
            context_after: Texto depois do parágrafo

        Returns:
            Tupla (texto corrigido, número de chamadas API feitas)
        """
        import re
        import time

        if not self.is_available():
            return text, 0

        # 1. Extrair todas as fórmulas do texto
        all_snippets = self._extract_formula_snippets(text)

        if not all_snippets:
            return text, 0

        total_formulas = len(all_snippets)
        chunk_size = self.config.formulas_per_call  # Padrão: 10
        max_calls = self.config.max_api_calls_per_file  # Padrão: 10

        # 2. Calcular número de chunks
        num_chunks = min(
            (total_formulas + chunk_size - 1) // chunk_size,
            max_calls
        )

        print(f"      📦 Batch: {total_formulas} fórmulas → {num_chunks} chunk(s) de até {chunk_size} cada", flush=True)

        # Limitar contexto para não sobrecarregar o prompt
        context_before = context_before[-300:] if len(context_before) > 300 else context_before
        context_after = context_after[:300] if len(context_after) > 300 else context_after

        result = text
        api_calls_made = 0

        # 3. Processar cada chunk
        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min(start_idx + chunk_size, total_formulas)
            chunk_snippets = all_snippets[start_idx:end_idx]

            chunk_num = chunk_idx + 1
            print(f"         🔄 Chunk {chunk_num}/{num_chunks} ({len(chunk_snippets)} fórmulas)...", end=" ", flush=True)

            # Criar prompt para o chunk
            formulas_list = []
            for snippet, start, end in chunk_snippets:
                formulas_list.append(snippet)

            # Prompt para múltiplas fórmulas
            batch_prompt = f"""Fix each mathematical formula in the following text snippets.
Return the converted formulas in the same order, one per line.

Context before: {context_before}
Context after: {context_after}

Formulas to convert:
{chr(10).join(f"{i+1}. {f}" for i, f in enumerate(formulas_list))}

Return ONLY the converted formulas, one per line, in the same order."""

            try:
                start_time = time.time()
                response = self._make_request(
                    system_prompt=CONTEXT_SYSTEM_PROMPT,
                    user_prompt=batch_prompt
                )

                # Limpar resposta
                response = re.sub(r'<think>.*?', '', response, flags=re.DOTALL).strip()
                if response.startswith("```"):
                    lines = response.split('\n')
                    response = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

                # Parsear respostas (uma por linha)
                converted_lines = [line.strip() for line in response.strip().split('\n') if line.strip()]
                # Remover numeração
                converted_lines = [re.sub(r'^\d+[\.\)\-]\s*', '', line).strip() for line in converted_lines]

                elapsed = time.time() - start_time
                print(f"✓ ({elapsed:.1f}s)", flush=True)

                api_calls_made += 1

                # 4. Substituir fórmulas no texto (de trás para frente para não deslocar posições)
                for i, (snippet, start, end) in enumerate(reversed(chunk_snippets)):
                    if i < len(converted_lines):
                        fixed = converted_lines[-(i+1)]  # Pegar na ordem reversa
                        if fixed and fixed != snippet and not fixed.startswith("Erro"):
                            # Calcular offset devido a mudanças anteriores
                            offset = len(result) - len(text)
                            adjusted_start = start + offset
                            adjusted_end = end + offset
                            if 0 <= adjusted_start < len(result) and adjusted_end <= len(result):
                                result = result[:adjusted_start] + fixed + result[adjusted_end:]

            except Exception as e:
                elapsed = time.time() - start_time if 'start_time' in locals() else 0
                print(f"✗ ({elapsed:.1f}s) - {str(e)[:30]}", flush=True)
                self._stats['errors'] += 1

        print(f"      ✅ Batch completo: {api_calls_made} chamada(s) API", flush=True)
        return result, api_calls_made

    def _make_request_with_timeout(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: int,
        session: 'requests.Session'
    ) -> str:
        """Faz requisição com timeout específico."""
        # Salvar sessão original
        old_session = self._session
        self._session = session
        
        # Salvar timeout original
        old_timeout = self.config.timeout
        self.config.timeout = timeout
        
        try:
            result = self._make_request(system_prompt, user_prompt)
            return result
        finally:
            # Restaurar
            self._session = old_session
            self.config.timeout = old_timeout

    def _parse_formula_responses(self, response: str, expected_count: int) -> List[str]:
        """
        Parseia as respostas do LLM para cada snippet.
        
        Espera uma resposta por linha, na mesma ordem dos snippets.
        """
        lines = [line.strip() for line in response.strip().split('\n') if line.strip()]
        
        # Remover numeração se presente ("1. " ou "1) ")
        import re
        results = []
        for line in lines:
            # Remover numeração no início
            cleaned = re.sub(r'^\d+[\.\)\-]\s*', '', line).strip()
            if cleaned:
                results.append(cleaned)
        
        # Se tivermos menos resultados que esperado, preencher com vazios
        while len(results) < expected_count:
            results.append("")
        
        # Se tivermos mais, truncar
        return results[:expected_count]

    def convert_batch(self, formulas: List[FormulaRequest]) -> List[FormulaResponse]:
        """
        Converte múltiplas fórmulas em uma única chamada API.

        Args:
            formulas: Lista de fórmulas para converter

        Returns:
            Lista de respostas
        """
        if not formulas:
            return []

        self._stats['requests'] += 1

        # Se API não disponível, retornar todas como falha
        if not self.is_available():
            return [
                FormulaResponse(
                    id=f.id,
                    original=f.original_text,
                    latex=f.original_text,
                    confidence=0.0,
                    success=False,
                    error="API key not configured"
                )
                for f in formulas
            ]

        # Agrupar em batches
        responses = []

        for i in range(0, len(formulas), self.config.batch_size):
            batch = formulas[i:i + self.config.batch_size]

            try:
                # Criar prompt de batch
                batch_prompt = self._create_batch_prompt(batch)

                # Fazer requisição
                response = self._make_request(
                    system_prompt=FORMULA_SYSTEM_PROMPT,
                    user_prompt=batch_prompt
                )

                # Parsear respostas
                batch_results = self._parse_batch_response(response, batch)
                responses.extend(batch_results)

            except Exception as e:
                logger.error(f"Erro no batch {i}: {e}")
                # Adicionar falhas para todo o batch
                responses.extend([
                    FormulaResponse(
                        id=f.id,
                        original=f.original_text,
                        latex=f.original_text,
                        confidence=0.0,
                        success=False,
                        error=str(e)
                    )
                    for f in batch
                ])

        self._stats['success'] = sum(1 for r in responses if r.success)
        self._stats['errors'] = sum(1 for r in responses if not r.success)

        return responses

    def _create_batch_prompt(self, formulas: List[FormulaRequest]) -> str:
        """Cria prompt para batch de fórmulas."""
        lines = []

        for i, formula in enumerate(formulas, 1):
            lines.append(f"{i}. {formula.original_text}")

        prompt = f"""Convert each of these mathematical formulas to LaTeX.
Return a JSON array with one object per formula:

[
  {{"id": "1", "latex": "...", "confidence": 0.95}},
  {{"id": "2", "latex": "...", "confidence": 0.90}}
]

Formulas:
{chr(10).join(lines)}

Return JSON only:"""

        return prompt

    def _make_request(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:
        """Faz requisição para API."""

        if self.config.provider == Provider.OPENAI:
            return self._openai_request(system_prompt, user_prompt)
        elif self.config.provider == Provider.ANTHROPIC:
            return self._anthropic_request(system_prompt, user_prompt)
        elif self.config.provider == Provider.GOOGLE:
            return self._google_request(system_prompt, user_prompt)
        elif self.config.provider == Provider.OLLAMA:
            return self._ollama_request(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")

    def _openai_request(self, system: str, user: str) -> str:
        """Requisição para OpenAI ou APIs compatíveis (como Minimax)."""
        import time
        
        url = self.config.api_url or "https://api.openai.com/v1/chat/completions"
        # Fix URLs that may be missing the /v1/chat/completions suffix
        if url.endswith('openai') or url.endswith('openai/'):
            url = url.rstrip('/') + '/v1/chat/completions'
        # Also handle Minimax URL without the full path
        elif 'minimax.io' in url and not url.endswith('/chat/completions'):
            url = url.rstrip('/') + '/v1/chat/completions'

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature
        }

        # Implementar retries para timeouts
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = self._session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Verificar formato da resposta
                if 'choices' not in data or not data['choices']:
                    raise ValueError(f"Resposta inválida da API: {data}")
                
                return data['choices'][0]['message']['content']
                
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"Timeout na tentativa {attempt + 1}/{self.config.max_retries} para {url}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(f"Erro de rede na tentativa {attempt + 1}: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise
        
        # Se todas as tentativas falharam
        if last_error:
            raise last_error
        raise RuntimeError("Falha desconhecida na requisição")

    def _anthropic_request(self, system: str, user: str) -> str:
        """Requisição para Anthropic."""
        url = self.config.api_url or "https://api.anthropic.com/v1/messages"
        if url.endswith('anthropic') or url.endswith('anthropic/'):
            url = url.rstrip('/') + '/v1/messages'

        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}]
        }

        response = self._session.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout
        )

        response.raise_for_status()
        data = response.json()

        return data['content'][0]['text']

    def _google_request(self, system: str, user: str) -> str:
        """Requisição para Google Gemini."""
        url = self.config.api_url or f"https://generativelanguage.googleapis.com/v1/models/{self.config.model}:generateContent"

        params = {"key": self.config.api_key}

        payload = {
            "contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens
            }
        }

        response = self._session.post(
            url,
            params=params,
            json=payload,
            timeout=self.config.timeout
        )

        response.raise_for_status()
        data = response.json()

        return data['candidates'][0]['content']['parts'][0]['text']

    def _ollama_request(self, system: str, user: str) -> str:
        """Requisição para Ollama local."""
        url = self.config.api_url or "http://localhost:11434/api/generate"

        payload = {
            "model": self.config.model,
            "prompt": f"{system}\n\n{user}",
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens
            }
        }

        response = self._session.post(
            url,
            json=payload,
            timeout=self.config.timeout
        )

        response.raise_for_status()
        data = response.json()

        return data.get('response', '')

    def _parse_response(self, response: str) -> Dict:
        """Parseia resposta individual."""
        try:
            # Tentar extrair JSON da resposta
            # Pode vir com markdown ou não
            response = response.strip()

            if response.startswith("```"):
                # Remover código markdown
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

            return json.loads(response)

        except json.JSONDecodeError as e:
            # Tentar extrair só a parte JSON
            import re
            match = re.search(r'\{[^{}]*\}', response)
            if match:
                return json.loads(match.group(0))
            raise ValueError(f"Invalid JSON response: {response[:100]}")

    def _parse_batch_response(
        self,
        response: str,
        formulas: List[FormulaRequest]
    ) -> List[FormulaResponse]:
        """Parseia resposta de batch."""
        try:
            # Parsear array JSON
            data = json.loads(response)

            if not isinstance(data, list):
                data = [data]

            # Mapear resultados para IDs
            result_map = {item['id']: item for item in data}

            responses = []
            for formula in formulas:
                result = result_map.get(formula.id, {})

                responses.append(FormulaResponse(
                    id=formula.id,
                    original=formula.original_text,
                    latex=result.get('latex', formula.original_text),
                    confidence=result.get('confidence', 0.0),
                    success=result.get('confidence', 0.0) > 0
                ))

            return responses

        except Exception as e:
            logger.error(f"Erro ao parsear batch: {e}")
            # Retornar falhas
            return [
                FormulaResponse(
                    id=f.id,
                    original=f.original_text,
                    latex=f.original_text,
                    confidence=0.0,
                    success=False,
                    error=str(e)
                )
                for f in formulas
            ]

    def get_stats(self) -> Dict:
        """Retorna estatísticas."""
        return self._stats.copy()


# =============================================================================
# Funções de conveniência
# =============================================================================

def get_api_converter() -> APIFormulaConverter:
    """Obtém instância do conversor API."""
    return APIFormulaConverter()


def convert_formula_with_api(formula: str) -> str:
    """
    Converte uma fórmula usando API.

    Args:
        formula: Texto da fórmula

    Returns:
        Fórmula em LaTeX
    """
    converter = get_api_converter()
    result = converter.convert(formula)
    return result.latex
