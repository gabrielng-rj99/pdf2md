# Documento de Análise: Tratamentos Diferenciais/Específicos

## Status: ATUALIZADO EM 2026-03-16

## Alterações Realizadas

### Remoções Confirmadas:

1. **app/services/pdf2md_service.py** (-312 linhas)
   - ✅ Removida função `detect_broken_formulas()` - padrões regex específicos
   - ✅ Removida função `fix_formulas_with_pdf_context()` - correções hardcoded
   - ✅ Removida função `_fix_formulas_single_call()` - regras específicas via API
   - ✅ Removida função `_fix_formulas_chunked()` - chunked version
   - ✅ Removida função `_apply_hardcoded_corrections()` - fallback específico
   - ✅ Removidas chamadas para essas funções no fluxo principal

2. **app/utils/math_postprocessor.py** (-3 linhas)
   - ✅ Removida chamada para `_fix_known_patterns()` na linha 106

### Não Removido (funções órfãs, não chamadas):
- `apply_brazilian_fixes()` - não chamada em nenhum lugar
- `aggressive_formula_cleanup()` - não chamada em nenhum lugar
- `_fix_known_patterns()` - não chamada (definição permanece mas não é executada)

---

## Resumo Final

| Componente | Status | Detalhes |
|------------|--------|----------|
| pdf2md_service.py | ✅ Limpo | 312 linhas de tratamento específico removidas |
| math_postprocessor.py | ✅ Limpo | 1 chamada específica removida |
| Testes unitários | ✅ Passando | 1003 testes passando |
| Testes integração | ✅ Passando | 34 testes passando |

## Visão Geral

---

## 1. CORE (app/core/md_formatter.py)

### Funções com tratamento específico:

| Função | Linhas | Tratamento Específico |
|--------|--------|----------------------|
| `_link_images_to_text` | 214-248 | Detecta referências: "Figura X", "Tabela X", "Imagem X", "Gráfico X" via regex |
| `detect_list_item` | 290-312 | Detecta listas com marcadores "-•*" e numeradas "1.", "1.1." via regex |
| `generate_markdown` | 185-212 | Normaliza 3+ quebras de linha → 2 |

---

## 2. SERVICES (app/services/pdf2md_service.py)

### Funções com tratamento específico:

| Função | Linhas | Tratamento Específico |
|--------|--------|----------------------|
| `detect_broken_formulas` | 276-319 | **REGEX PATTERNS HARDCODED** |
| | | - `\\gammar` → detecta como erro |
| | | - `kgf/m³` → detecta sem formato |
| | | - `N/m³` → detecta sem formato |
| | | - `(?<!^)\bm³\b` → detecta m³ sem expoente |
| | | - `\$\s*PV\s*=\s*\$` → detecta PV = incompleta |
| | | - `\$\s*=\s*\$` → detecta equação incompleta |
| | | - `\bnRT\b` → detecta nRT sem formato |
| | | - `\$[^$]*\\rho\b(?!_\|{` → detecta rho sem escape |
| | | - `\$[^$]*\\epsilon\b(?!_\|{` → detecta epsilon sem escape |
| | | - `\\gamma(?!\w)` → detecta gamma sem escape |
| `fix_formulas_with_pdf_context` | 458-507 | **CORREÇÕES HARDCODED** |
| | | - `\\gammar` → `\\gamma_r` |
| | | - `kgf/m³` → `kgf/m^3` |
| | | - `N/m³` → `N/m^3` |
| | | - `m³` → `m^3` |
| `_fix_formulas_single_call` | 510-579 | Envia regras específicas para API |
| `_fix_formulas_chunked` | 582-670+ | Chunked version das regras acima |
| `_apply_hardcoded_corrections` | 791-810 | Fallback com correções regex |

---

## 3. UTILS (app/utils/)

### 3.1 math_postprocessor.py

| Função | Linhas | Tratamento Específico |
|--------|--------|----------------------|
| `_fix_joined_words` | 147-182 | Palavras grudadas de mecânica dos fluidos |
| `_fix_broken_words_in_line` | 184-228 | Lista hardcoded: Federal, Universidade, Juiz, Fora, etc |
| `_fix_greek_spacing` | 272-294 | Símbolos gregos: ρ, μ, γ, ν, ε, σ, π, τ, φ, ω, α, β, δ, λ, θ |
| `_fix_symbol_word_joining` | 296-316 | Lista hardcoded: valor, módulo, coeficiente, etc |
| `_fix_known_patterns` | 622-882 | **MUITO ESPECÍFICO** |
| | | - ρ = m/V fragmentada (linhas 644-654) |
| | | - γ = G/V fragmentada (linhas 656-666) |
| | | - Volume específico fragmentado (linhas 669-678) |
| | | - Sistemas MKS/CGS/MK*S (linhas 685-716) |
| | | - kgf/m³ fragmentado (linhas 757-758) |
| | | - "O" e "A" grudados (linhas 788-831) |
| `aggressive_formula_cleanup` | 939-977 | - m/V massa/volume (950-952) |
| | | - G/V peso/volume (954-956) |
| | | - P/R pressão/temperatura (958-960) |
| | | - Sistema MK*S (962-964) |
| | | - H2O → H₂O (966-968) |
| `apply_brazilian_fixes` | 1020-1037 | - UFJF, UFMG, USP, UNICAMP |
| | | - kgf, m/s², N/m², Pascal |
| | | - Hidrostática, Hidrodinâmica, Termodinâmica |

### 3.2 text_cleaner.py

| Função | Linhas | Tratamento Específico |
|--------|--------|----------------------|
| `classify_text` + `_calculate_formula_score` | 341-484 | Letras gregas: alpha, beta, gamma, delta, etc |
| | | Funções matemáticas em português: sen, cos, tan, log, ln, exp |
| | | Unidades: kg, m, s, N, Pa, J, W, Hz, mol, K, A, cd, rad, sr, kgf, cm, mm, km, g, mg, kPa, MPa, GPa |
| | | Variáveis de física: V, P, T, R, F, A, M, E |
| `FormulaReconstructor.text_to_latex` | 690-726 | LATEX_MAP com letras gregas |
| | | Funções em português: sen→\sin, tg→\tan, log→\log, ln→\ln |

### 3.3 formula_detector.py

| Função | Linhas | Tratamento Específico |
|--------|--------|----------------------|
| `_detect_equations` | 232-257 | Regex com letras gregas inclusas: α-ωΑ-Ω |
| `_is_common_abbreviation` | 469-475 | Lista: e/ou, km/h, m/s, kg/m, n/a, a/c, c/c, s/n, i/o, w/o, b/w, r/w |
| `_detect_chemical_formulas` | 590-632 | Elementos químicos listados: H, He, Li, Be, B, C, N, O, F, Ne, Na, Mg... |

### 3.4 api_formula_converter.py

| Função | Linhas | Tratamento Específico |
|--------|--------|----------------------|
| `_extract_formula_snippets` | 277-337 | Caracteres Unicode privados PDF |
| | | Letras gregas: αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ |
| | | **Bhaskara específico**: [-–−]?[\s]*[bβ][\s]*[±\+\-][\s]*√[\s]*[Δb] |
| | | **Delta Bhaskara**: [ΔΔ][\s]*[=＝]?[\s]*[bβ]?[\s]*²?[\s]*[\-–−]?[\s]*4[\s]*[aα][\s]*[cγ] |
| | | Definições com ρ (massa específica), γ (peso específico) |

### 3.5 latex_converter.py

| Função | Linhas | Tratamento Específico |
|--------|--------|----------------------|
| `_convert_fractions` | 390-432 | Mantém "a/b" se ≤3 caracteres |
| `_format_functions` | 455-480 | sen→\operatorname{sen} (português) |

### 3.6 surgical_latex_converter.py

| Função | Linhas | Tratamento Específico |
|--------|--------|----------------------|
| `_convert_greek` | 315-333 | Greek + letra específico |
| `PORTUGUESE_FUNCTIONS` | 141-148 | sen→\sin, tg→\tan, cotg→\cot, cossec→\csc, arcsen→\arcsin, arctg→\arctan |

### 3.7 math_span_detector.py

| Função | Linhas | Tratamento Específico |
|--------|--------|----------------------|
| `NON_MATH_WORDS` | 131-139 | Palavras não-matemáticas: de, da, do, que, para, por, the, a, an, of, in, on |
| `_is_false_positive` | 579-602 | Falsos positivos: e-mail, on-line, off-line, check-in, check-out, know-how, up-to-date |

---

## 4. TESTES RELACIONADOS A APAGAR

### Arquivos de teste que devem ser removidos ou modificados:

| Arquivo de Teste | Funções Afetadas |
|------------------|------------------|
| `test_formula_context.py` | TODO - testar se esse arquivo é específico |
| `test_formula_detector.py` | Funções genéricas de detecção |
| `test_formula_reconstruction.py` | Funções genéricas de reconstrução |
| `test_latex_converter.py` | Funções genéricas de conversão |
| `test_math_zone_detector.py` | Funções genéricas |
| `test_math_modules.py` | Contém testes específicos ρ = m/V, γ = ρg |
| `test_llm_formula_converter.py` | Funções genéricas |
| `test_formula_ai.py` | Funções genéricas |
| `test_formula_merger.py` | Funções genéricas |

---

## RESUMO: O QUE REMOVER

### 1. Em pdf2md_service.py (linhas ~276-319, ~458-507, ~510-669, ~791-810):
- `detect_broken_formulas()` - TODOS os regex patterns específicos
- `fix_formulas_with_pdf_context()` - TODAS as correções hardcoded
- `_fix_formulas_single_call()` - REGRAS específicas enviadas à API
- `_fix_formulas_chunked()` - Mesmo que acima
- `_apply_hardcoded_corrections()` - Fallback específico

### 2. Em math_postprocessor.py:
- `_fix_known_patterns()` - Padrões específicos de mecânica dos fluidos
- `aggressive_formula_cleanup()` - Limpeza específica
- `apply_brazilian_fixes()` - Correções brasileiras

### 3. Em text_cleaner.py:
- `_calculate_formula_score()` - Listas hardcoded de variáveis

### 4. Testes relacionados:
- Verificar e remover/modificar testes que dependem desses padrões específicos
