# FormulaDetector - Detecção e Formatação de Fórmulas Matemáticas

## 📋 Visão Geral

O **FormulaDetector** é um módulo leve para detectar e formatar expressões matemáticas em texto extraído de PDFs, convertendo-as para formato LaTeX compatível com Markdown (GitHub/Obsidian/MarkText).

### Características

- ✅ **Leve** - Sem dependências de ML/LLM
- ✅ **Rápido** - Baseado em regex e heurísticas
- ✅ **Compatível** - Formato LaTeX padrão (`$...$` e `$$...$$`)
- ✅ **Configurável** - Parâmetros ajustáveis
- ✅ **Testado** - 75 testes unitários

## 🚀 Início Rápido

### Uso Básico

```python
from app.utils.formula_detector import FormulaDetector

# Criar detector
detector = FormulaDetector()

# Processar texto
text = "A área é A = πr² e o volume é V = 4/3πr³"
result = detector.process_text(text)
# Resultado contém fórmulas formatadas com $...$ e $$...$$
```

### Função de Conveniência

```python
from app.utils.formula_detector import detect_and_format_formulas

result = detect_and_format_formulas("E = mc²")
```

### Verificação Rápida

```python
from app.utils.formula_detector import is_math_expression

if is_math_expression("x = y + z"):
    print("É uma expressão matemática!")
```

## 📊 Formatos Suportados

### Inline (`$...$`)

Fórmulas curtas no meio do texto:

| Original | Resultado |
|----------|-----------|
| `x^2` | `$x^{2}$` |
| `α + β` | `$\alpha + \beta$` |
| `kg/m³` | `$\frac{kg}{m^{3}}$` |

### Bloco (`$$...$$`)

Fórmulas longas ou equações completas:

```
$$
E = mc^{2}
$$
```

O threshold padrão para bloco é 50 caracteres.

## 🔧 Configuração

### Parâmetros Disponíveis

```python
from app.utils.formula_detector import FormulaDetector, FormulaDetectorConfig

config = FormulaDetectorConfig(
    # Thresholds
    min_confidence=0.5,          # Confiança mínima (0.0 a 1.0)
    min_operators=1,             # Mínimo de operadores
    
    # Detecção
    detect_fractions=True,       # Detectar frações (a/b)
    detect_subscripts=True,      # Detectar índices (x_1)
    detect_superscripts=True,    # Detectar potências (x^2)
    detect_greek=True,           # Detectar letras gregas
    detect_special_functions=True, # Detectar sin, cos, log, etc.
    
    # Formatação
    block_threshold=50,          # Caracteres para bloco
    wrap_inline=True,            # Envolver com $...$
    wrap_block=True,             # Envolver com $$...$$
    
    # Filtros
    max_length=500,              # Comprimento máximo
    min_length=3,                # Comprimento mínimo
)

detector = FormulaDetector(config)
```

## 📝 Detecção Suportada

### Letras Gregas

| Unicode | LaTeX |
|---------|-------|
| α | `\alpha` |
| β | `\beta` |
| γ | `\gamma` |
| δ | `\delta` |
| π | `\pi` |
| ρ | `\rho` |
| σ | `\sigma` |
| ω | `\omega` |
| Σ | `\Sigma` |
| Δ | `\Delta` |
| Ω | `\Omega` |

### Operadores Matemáticos

| Unicode | LaTeX |
|---------|-------|
| × | `\times` |
| ÷ | `\div` |
| ± | `\pm` |
| ≠ | `\neq` |
| ≈ | `\approx` |
| ≤ | `\leq` |
| ≥ | `\geq` |
| ∞ | `\infty` |
| ∑ | `\sum` |
| ∫ | `\int` |
| √ | `\sqrt` |

### Funções Matemáticas

- Trigonométricas: `sin`, `cos`, `tan`, `cot`, `sec`, `csc`
- Logarítmicas: `log`, `ln`, `exp`
- Limites: `lim`, `max`, `min`, `sup`, `inf`
- Outras: `det`, `dim`, `ker`, `deg`, `gcd`, `lcm`, `mod`
- Português: `sen`, `tg`, `cotg`, `cossec`

### Padrões Detectados

1. **Equações**: `x = y + z`
2. **Frações**: `a/b`, `(x+1)/(y-1)`
3. **Potências**: `x^2`, `x^{n+1}`
4. **Índices**: `x_1`, `x_{i,j}`
5. **Funções**: `sin(x)`, `log_2(x)`

## 📊 Estruturas de Dados

### FormulaType (Enum)

```python
class FormulaType(Enum):
    INLINE = "inline"   # Fórmula no meio do texto
    BLOCK = "block"     # Fórmula em bloco separado
```

### Formula (Dataclass)

```python
@dataclass
class Formula:
    original: str           # Texto original
    latex: str              # Expressão LaTeX
    formula_type: FormulaType
    confidence: float       # 0.0 a 1.0
    start_pos: int          # Posição inicial
    end_pos: int            # Posição final
```

## 🔍 Métodos Principais

### `detect_formulas(text: str) -> List[Formula]`

Detecta todas as fórmulas em um texto.

```python
formulas = detector.detect_formulas("A = πr²")
for f in formulas:
    print(f"Original: {f.original}")
    print(f"LaTeX: {f.latex}")
    print(f"Confiança: {f.confidence}")
```

### `process_text(text: str) -> str`

Processa texto e substitui fórmulas por LaTeX formatado.

```python
result = detector.process_text("Onde ρ = m/V")
# "Onde $\rho = \frac{m}{V}$"
```

### `is_formula_line(text: str) -> bool`

Verifica se uma linha inteira é uma fórmula.

```python
if detector.is_formula_line("E = mc²"):
    print("Esta linha é uma fórmula")
```

### `format_formula_block(text: str) -> str`

Formata uma fórmula como bloco LaTeX.

```python
block = detector.format_formula_block("x = y + z")
# "$$\nx = y + z\n$$"
```

## ⚙️ Sistema de Confiança

O detector calcula uma confiança (0.0 a 1.0) para cada fórmula:

### Fatores Positivos

| Fator | Peso |
|-------|------|
| Tem sinal `=` | +0.3 |
| Operadores matemáticos | +0.1 cada (max 0.3) |
| Letras gregas/símbolos | +0.1 cada (max 0.2) |
| Padrão de variável | +0.1 |

### Fatores Negativos

| Fator | Peso |
|-------|------|
| Palavras comuns (de, da, the) | -0.15 cada |

## 🧪 Testes

### Executar Testes

```bash
# Todos os testes do detector
pytest tests/unit/test_formula_detector.py -v

# Testes específicos
pytest tests/unit/test_formula_detector.py::TestEquationDetection -v
pytest tests/unit/test_formula_detector.py::TestLatexConversion -v
```

### Cobertura

- ✅ 75 testes unitários
- ✅ Testes de detecção (equações, frações, potências, funções)
- ✅ Testes de conversão LaTeX
- ✅ Testes de configuração
- ✅ Testes de edge cases
- ✅ Testes com exemplos reais

## 📁 Arquivos

```
app/utils/
└── formula_detector.py        # Módulo principal

tests/unit/
└── test_formula_detector.py   # Testes unitários

docs/
└── FORMULA_DETECTOR.md        # Esta documentação
```

## 🔄 Integração com o Pipeline

O FormulaDetector está integrado ao `pdf2md_service.py`:

```python
# Em consolidate_text_blocks()
formula_detector = FormulaDetector(config)

# Processar fórmulas em parágrafos
paragraph_text = formula_detector.process_text(paragraph_text)

# Detectar linhas que são fórmulas completas
if formula_detector.is_formula_line(text):
    paragraphs.append(formula_detector.format_formula_block(text))
```

## 🐛 Troubleshooting

### Fórmulas Não Detectadas

Reduza a confiança mínima:

```python
config = FormulaDetectorConfig(min_confidence=0.3)
```

### Muitos Falsos Positivos

Aumente a confiança mínima:

```python
config = FormulaDetectorConfig(min_confidence=0.7)
```

### Frações Comuns Detectadas como Fórmulas

Abreviações comuns como `km/h`, `e/ou` são filtradas automaticamente. Para adicionar mais:

```python
# No código, adicione ao conjunto _is_common_abbreviation()
```

## 📝 Limitações

1. **OCR Ruim**: Fórmulas mal escaneadas podem não ser detectadas
2. **Fórmulas Complexas**: Matrizes, sistemas de equações não são suportados
3. **Contexto Limitado**: Não analisa contexto semântico profundo
4. **Sem ML**: Detecção baseada apenas em padrões

## 📈 Exemplos de Saída

### Entrada (PDF)
```
A massa específica (kg/m³) é definida como ρ = m/V
```

### Saída (Markdown)
```
A massa específica ($\frac{kg}{m^{3}}$) é definida como $\rho = \frac{m}{V}$
```

### Renderizado
A massa específica ($\frac{kg}{m^{3}}$) é definida como $\rho = \frac{m}{V}$

---

**Autor:** Projeto pdf2md  
**Última atualização:** Dezembro 2025