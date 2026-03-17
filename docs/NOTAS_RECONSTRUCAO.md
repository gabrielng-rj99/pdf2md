# Notas sobre Reconstrução de Fórmulas

## Status Atual

O módulo de reconstrução de fórmulas (`app/utils/formula_reconstruction.py`) foi implementado mas **NÃO está integrado** ao pipeline principal.

### Por quê?

O PyMuPDF fragmenta fórmulas durante a extração de texto de PDFs complexos. Exemplos:
- "temperatu" em vez de "temperatura"
- "constantel" em vez de "constante"  
- "volume massa sendo" (fórmula fragmentada)

### O que foi tentado?

1. **Heurísticas de agrupamento**: Tentou agrupar fragmentos por proximidade
2. **Classificação de tipos**: Identificou operadores, variáveis, subscritos
3. **Conversão para LaTeX**: Converteu símbolos Unicode

### Resultado

- ✅ **Overhead**: Praticamente zero (-0.8%)
- ❌ **Qualidade**: Não melhorou significativamente
- ⚠️ **Limitação**: PyMuPDF já entrega fragmentado demais

### Solução Real

Para resolver completamente, seria necessário:
1. **OCR Math-aware** (LaTeX-OCR, MathPix)
2. **Renderização visual** das fórmulas
3. **Análise de layout 2D** do PDF

## Arquivos

- `app/utils/formula_reconstruction.py` - Módulo (não integrado)
- `tests/unit/test_formula_reconstruction.py` - 49 testes
- `scripts/benchmark_formula_reconstruction.py` - Benchmark

## Como usar (caso queira testar)

```python
from app.utils.formula_reconstruction import reconstruct_formulas

text = "E\n=\nmc²"
result = reconstruct_formulas(text)
# Retorna: "E = mc²"
```

## Recomendação

**Manter desabilitado** até ter uma solução real (OCR especializado).
