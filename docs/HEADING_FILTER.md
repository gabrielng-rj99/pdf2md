# HeadingFilter - Detecção Inteligente de Headings

Documentação completa do módulo `heading_filter` para detecção e classificação automática de headings (H1-H6) em documentos PDF convertidos para Markdown.

## 📋 Visão Geral

O `HeadingFilter` é um módulo avançado que detecta e hierarquiza títulos em PDFs usando **apenas tamanho de fonte** como métrica principal, sem depender de análise de texto ou modelos de linguagem.

### Características Principais

- ✅ **Detecção por Tamanho de Fonte**: O maior tamanho vira H1, o menor vira H6
- ✅ **Filtragem Inteligente**: Remove rodapés, cabeçalhos, repetições e textos genéricos
- ✅ **Normalização Robusta**: Agrupa tamanhos similares (dentro de 0.5pt)
- ✅ **Validação Completa**: Valida comprimento, conteúdo e posição do texto
- ✅ **Sem Dependências Externas**: Usa apenas stdlib do Python
- ✅ **100% Testado**: 60+ testes de cobertura

## 🏗️ Arquitetura

### Fluxo de Processamento

```
Texto extraído do PDF
         ↓
HeadingCandidate (texto + tamanho + posição)
         ↓
Validação de Entrada
    ├─ Tamanho de fonte válido (10-72pt)
    ├─ Texto válido (2-200 caracteres, com letras)
    ├─ Não é genérico (Sumário, Introdução, etc)
    ├─ Não está em margem (top 5%, bottom 8%)
    └─ Não é duplicata
         ↓
Agrupamento de Tamanhos
    └─ Agrupar tamanhos similares (±0.5pt)
         ↓
Mapeamento para Níveis
    └─ 1º tamanho → H1
    └─ 2º tamanho → H2
    └─ ...
    └─ 6º+ tamanho → H6
         ↓
Heading (texto + nível + metadados)
```

### Componentes

#### `HeadingCandidate`
Representa um candidato bruto a heading com todos os dados necessários.

```python
@dataclass
class HeadingCandidate:
    text: str                                      # Texto do candidato
    font_size: float                               # Tamanho em pontos
    page_num: int                                  # Número da página
    bbox: Tuple[float, float, float, float]        # (x0, y0, x1, y1)
    y_ratio: float                                 # Posição vertical (0.0-1.0)
```

#### `Heading`
Representa um heading validado e classificado.

```python
@dataclass
class Heading:
    text: str                                      # Texto do heading
    level: int                                     # Nível 1-6
    page_num: int                                  # Página de origem
    font_size: float                               # Tamanho original
    position: Tuple[float, float, float, float]    # Bounding box
```

#### `HeadingFilter`
Classe principal que implementa toda a lógica de detecção e classificação.

## 🚀 Uso Básico

### Exemplo Simples

```python
from app.utils.heading_filter import HeadingFilter, HeadingCandidate

# Criar instância do filtro
hf = HeadingFilter()

# Preparar candidatos (simulando extração de PDF)
candidates = [
    HeadingCandidate(
        text="Capítulo 1: Introdução",
        font_size=28.0,
        page_num=1,
        bbox=(10, 50, 300, 100),
        y_ratio=0.15
    ),
    HeadingCandidate(
        text="Seção 1.1",
        font_size=22.0,
        page_num=1,
        bbox=(10, 150, 250, 180),
        y_ratio=0.25
    ),
    HeadingCandidate(
        text="Subsection",
        font_size=16.0,
        page_num=1,
        bbox=(10, 250, 200, 270),
        y_ratio=0.35
    ),
]

# Filtrar e classificar headings
headings = hf.filter_headings(candidates)

# Usar resultados
for heading in headings:
    print(f"{'#' * heading.level} {heading.text}")
    # Saída:
    # # Capítulo 1: Introdução
    # ## Seção 1.1
    # ### Subsection
```

### Exemplo com Página Customizada

```python
# Para PDFs com altura de página diferente (A4 landscape)
hf = HeadingFilter(page_height=612.0)  # 8.5" em pontos

headings = hf.filter_headings(candidates)
```

## 🔧 API Reference

### Método Principal: `filter_headings()`

```python
def filter_headings(self, candidates: List[HeadingCandidate]) -> List[Heading]:
    """
    Filtra uma lista de candidatos e retorna headings validados.
    
    Esta é a função principal do módulo.
    
    Args:
        candidates: Lista de HeadingCandidate brutos
    
    Returns:
        Lista de Heading validados e classificados
    
    Raises:
        Nenhuma (retorna [] se entrada inválida)
    """
```

**Exemplo:**
```python
headings = hf.filter_headings(candidates)
assert all(h.level >= 1 and h.level <= 6 for h in headings)
assert all(h.text for h in headings)
```

### Método Auxiliar: `get_heading_level()`

```python
def get_heading_level(self, font_size: float) -> Optional[int]:
    """
    Retorna o nível de heading para um tamanho de fonte.
    
    Args:
        font_size: Tamanho da fonte em pontos
    
    Returns:
        Nível de heading (1-6) ou None se não for heading
    """
```

**Exemplo:**
```python
hf.filter_headings(candidates)  # Primeiro, deve chamar filter_headings
level = hf.get_heading_level(28.0)  # Retorna 1 (se 28.0 for o maior tamanho)
```

### Método Auxiliar: `get_statistics()`

```python
def get_statistics(self) -> Dict[str, any]:
    """
    Retorna estatísticas sobre o mapeamento de headings.
    
    Returns:
        Dicionário com estatísticas de mapeamento
    """
```

**Exemplo:**
```python
stats = hf.get_statistics()
# {
#     "total_sizes": 3,
#     "size_to_level": {28.0: 1, 22.0: 2, 16.0: 3},
#     "total_seen_texts": 3,
#     "page_height": 792.0
# }
```

## 🔍 Filtros Aplicados

### 1. Validação de Tamanho de Fonte

```
MIN_FONT_SIZE = 10.0pt    ← Muito pequeno para heading
MAX_FONT_SIZE = 72.0pt    ← Limite superior razoável
```

Headings com tamanho fora desse intervalo são rejeitados.

### 2. Validação de Texto

```
Mínimo: 2 caracteres
Máximo: 200 caracteres
Deve ter: Pelo menos uma letra (a-z, á-ú, etc)
Não aceita: Apenas números ou símbolos
```

### 3. Títulos Genéricos

Textos como "Sumário", "Introdução", "Conclusão", "Referências" são ignorados por serem genéricos.

**Lista completa** (português e inglês):
- sumário, índice, table of contents
- introdução, introduction
- conclusão, conclusion
- referências, references
- apêndice, appendix
- prefácio, preface
- agradecimentos, acknowledgments
- prólogo, prologue
- nota, notes
- observação, observations

### 4. Detecção de Rodapé/Cabeçalho

```
HEADER_THRESHOLD = 0.05  (top 5%)
FOOTER_THRESHOLD = 0.92  (bottom 8%)
```

Textos nessas posições são filtrados automaticamente.

### 5. Remoção de Duplicatas

Textos duplicados (mesma normalização) aparecem apenas uma vez.

**Normalização:**
- Remove espaços extras
- Converte para minúsculas
- Preserva acentos e caracteres especiais

### 6. Agrupamento de Tamanhos Similares

```
FONT_SIZE_TOLERANCE = 0.5pt
```

Tamanhos dentro de ±0.5pt são agrupados no mesmo nível de heading.

## 📊 Exemplos Avançados

### Exemplo 1: Processamento de PDF Real

```python
import fitz  # PyMuPDF
from app.utils.heading_filter import HeadingFilter, HeadingCandidate

def extract_heading_candidates(pdf_path: str) -> List[HeadingCandidate]:
    """Extrai candidatos a heading de um PDF."""
    doc = fitz.open(pdf_path)
    candidates = []
    
    for page_num, page in enumerate(doc, 1):
        page_height = page.rect.height
        text_dict = page.get_text("dict")
        
        for block in text_dict["blocks"]:
            if "lines" not in block:
                continue
            
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    
                    font_size = span["size"]
                    bbox = span["bbox"]
                    y_ratio = bbox[1] / page_height
                    
                    candidates.append(HeadingCandidate(
                        text=text,
                        font_size=font_size,
                        page_num=page_num,
                        bbox=bbox,
                        y_ratio=y_ratio
                    ))
    
    return candidates

# Usar
candidates = extract_heading_candidates("documento.pdf")
hf = HeadingFilter()
headings = hf.filter_headings(candidates)

# Gerar Markdown
markdown = "\n".join(f"{'#' * h.level} {h.text}" for h in headings)
print(markdown)
```

### Exemplo 2: Estatísticas de Documento

```python
hf = HeadingFilter()
headings = hf.filter_headings(candidates)

# Análise de hierarquia
from collections import Counter
level_distribution = Counter(h.level for h in headings)

print(f"Total de headings: {len(headings)}")
print(f"Distribuição por nível:")
for level in sorted(level_distribution.keys()):
    count = level_distribution[level]
    print(f"  H{level}: {count} títulos")

# Estatísticas internas
stats = hf.get_statistics()
print(f"\nMapeamento de tamanhos:")
for size, level in sorted(stats["size_to_level"].items()):
    print(f"  {size:.1f}pt → H{level}")
```

### Exemplo 3: Teste de Robustez

```python
# Teste com PDFs malformados
candidates_messy = [
    # Válidos
    HeadingCandidate("Capítulo 1", 28.0, 1, (0, 50, 300, 100), 0.15),
    # Rejeitados
    HeadingCandidate("", 24.0, 1, (0, 150, 200, 180), 0.25),  # Vazio
    HeadingCandidate("A", 22.0, 1, (0, 200, 150, 220), 0.30),  # Muito curto
    HeadingCandidate("Introdução", 20.0, 1, (0, 250, 250, 270), 0.35),  # Genérico
    HeadingCandidate("Header Text", 18.0, 1, (0, 10, 200, 30), 0.02),  # Cabeçalho
]

hf = HeadingFilter()
headings = hf.filter_headings(candidates_messy)

# Apenas 1 heading válido
assert len(headings) == 1
assert headings[0].text == "Capítulo 1"
assert headings[0].level == 1
```

## 🧪 Testes

### Executar Testes

```bash
# Todos os testes
pytest tests/unit/test_heading_filter.py -v

# Testes específicos
pytest tests/unit/test_heading_filter.py::TestHeadingFilterSizeMapping -v

# Com coverage
pytest tests/unit/test_heading_filter.py --cov=app.utils.heading_filter
```

### Cobertura

Suíte com **60+ testes** cobrindo:
- ✅ Criação de candidatos e headings
- ✅ Validação de entrada
- ✅ Detecção de títulos genéricos
- ✅ Detecção de margens (rodapé/cabeçalho)
- ✅ Normalização de texto
- ✅ Agrupamento de tamanhos
- ✅ Mapeamento de níveis
- ✅ Filtragem completa
- ✅ Estatísticas

## ⚡ Performance

**Complexidade:**
- Extração de tamanhos: O(n)
- Agrupamento: O(n²) no pior caso, mas geralmente O(n log n)
- Filtragem: O(n)
- **Total: O(n²)** mas linear na prática

**Tempo típico:**
- 1000 candidatos: < 10ms
- 10000 candidatos: < 100ms

## 🔧 Configuração

Ajuste constantes na classe `HeadingFilter`:

```python
class HeadingFilter:
    # Textos genéricos (adicione mais conforme necessário)
    GENERIC_TITLES = {...}
    
    # Limites de tamanho de fonte
    MIN_FONT_SIZE = 10.0
    MAX_FONT_SIZE = 72.0
    
    # Tolerância para agrupamento
    FONT_SIZE_TOLERANCE = 0.5
    
    # Limites de margem
    HEADER_THRESHOLD = 0.05
    FOOTER_THRESHOLD = 0.92
```

## 🚨 Limitações Conhecidas

1. **Apenas Tamanho de Fonte**: Não analisa negrito, itálico ou cor
2. **Máximo 6 Níveis**: PDFs com mais níveis são comprimidos em H6
3. **Sem Contexto Textual**: Não analisa conteúdo, apenas metadados
4. **Página Padrão A4**: Assume 792pt de altura; customize se necessário

## 📚 Integração com pdf2md

O `HeadingFilter` foi projetado para integração futura no fluxo principal:

```python
# Em app/services/pdf2md_service.py (futuro)
from app.utils.heading_filter import HeadingFilter, HeadingCandidate

def extract_with_headings(pdf_path: str):
    # ... extração normal ...
    
    # Extrair candidatos de heading
    candidates = extract_candidates_from_pdf(pdf_path)
    
    # Filtrar e classificar
    hf = HeadingFilter()
    headings = hf.filter_headings(candidates)
    
    # Usar para estruturação do Markdown
    markdown_formatter.add_heading(h.text, h.level, h.page_num)
```

## 🤝 Contribuindo

Para melhorias:
1. Adicione títulos genéricos à lista `GENERIC_TITLES`
2. Ajuste limites (`MIN_FONT_SIZE`, `FONT_SIZE_TOLERANCE`) conforme necessário
3. Crie testes para novos cenários
4. Documente casos especiais

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique a [suite de testes](../../tests/unit/test_heading_filter.py)
2. Consulte exemplos acima
3. Verifique logs com `logger.debug()` habilitado