# Relatório de Tentativas - Correção de Fórmulas com IA

## Visão Geral

Este documento descreve as múltiplas tentativas realizadas para implementar um sistema de correção automática de fórmulas matemáticas usando APIs de IA (MiniMax), incluindo os problemas encontrados, aprendizados e a solução final adotada.

---

## Tentativa 1: Correção Line-by-Line com Arquivos Temporários

### Abordagem
- Criar arquivos temporários com fórmulas quebradas + contexto
- API corrige cada bloco individualmente
- Parsear resposta e fazer merge linha a linha

### Problemas
1. **API retornando thinking blocks**: A API MiniMax retornava `<thinking>...</thinking>` junto com JSON, causando erros de parse
2. **Respostas vazias**: Arquivo `@@ FIXED:` sempre vinha vazio
3. **Regex de limpeza não funcionava**: Padrão `r'<think>.*?
</think>'` tinha erro de sintaxe (newlines no raw string)

### Código Exemplo
```python
prompt = """FOR EACH BLOCK below:
1. Replace "@@ BROKEN: <text>" with "@@ FIXED: <corrected_text>"
2. Keep all other lines exactly the same
...
"""
```

### Aprendizado
- A API não estava seguindo o formato solicitado
- Necessário limpar thinking blocks antes de parsear

---

## Tentativa 2: Prompt Mais Simples

### Abordagem
- Simplificar o prompt para ser mais direto
- Reduzir complexidade do formato de entrada/saída

### Problemas
-仍然 retornando respostas vazias
- Timeout de 60s insuficiente para o tamanho do input

### Aprendizado
- A API precisa de prompts mais curtos e específicos
- Necessário aumentar timeout para PDFs grandes

---

## Tentativa 3: PDF como Referência + Markdown Inteiro

### Abordagem
- Usar PDF original como referência + Markdown completo como input
- Uma única chamada API para corrigir tudo

### Problemas
1. **Timeout**: 60s insuficiente (~50k tokens de input)
2. **Custo**: Input muito grande para API
3. **Resposta inconsistente**: API nem sempre retornava markdown válido

### Código
```python
prompt = f"""Analise o Markdown com fórmulas e compare com o texto de referência do PDF...
TEXTO DO PDF (referência):
{pdf_text[:10000]}...
MARKDOWN COM FÓRMULAS (corrigir):
{markdown_content}
...
"""
```

### Aprendizado
- Necessário chunking para textos grandes
- Precisa de fallback quando API falha

---

## Tentativa 4: Chunking com Tasks.md

### Abordagem
- Dividir markdown em chunks menores (~8k tokens cada)
- Criar arquivo tasks.md para rastrear progresso
- Processar cada chunk separadamente
- Unir resultados no final

### Problemas
1. **Timeout**: Mesmo com chunking, 60s era insuficiente
2. **Erro de código**: `regex_module` não definido em uma das funções
3. **Custo acumulado**: Múltiplas chamadas = custo alto

### Código
```python
CHUNK_SIZE = 35000  # ~8-10k tokens
if len(chunks) > 3:
    # Criar tasks.md
    with open(tasks_file, 'w') as f:
        f.write(f"# Tarefas de Correção de Fórmulas\n")
```

### Aprendizado
- Timeout precisa ser >= 120s para APIs deLLM
- Código precisa de imports consistentes
- Chunking pode funcionar mas precisa de otimização

---

## Tentativa 5: API com Timeout Aumentado (120s)

### Abordagem
- Aumentar timeout para 120 segundos
- Usar chunking com timeout maior

### Problemas
- **Ainda muito lento**: Cada chunk demorava ~60-90s
- **Inviável para produção**: 3 chunks = ~4 minutos só para correção de fórmulas

### Aprendizado
- APIs deLLM não são adequadas para correção em tempo real de PDFs grandes
- Precisamos de abordagem mais eficiente

---

## Tentativa 6: Regex Direto (Solução Atual)

### Abordagem
- Abandonar API por velocidade
- Usar regex para correções conhecidas e frequentes

### Resultado
- ✅ Rápido (~1 segundo)
- ✅ Correções aplicadas: 7 (gammar, kgf/m³, N/m³, m³)
- ✅ Sem timeout
- ✅ Sem custo de API

### Código
```python
def fix_formulas_with_pdf_context(pdf_path, markdown_content, output_dir):
    corrections = [
        (r'\\gammar(?!\w)', r'\\gamma_r'),
        (r'kgf/m³', 'kgf/m^3'),
        (r'N/m³', 'N/m^3'),
        (r'(?<!\w)m³(?!\^)', 'm^3'),
    ]
    # Aplicar todas as correções
```

### Vantagens
1. **Velocidade**: Processamento em segundos
2. **Confiabilidade**: Sem dependência de API externa
3. **Custo zero**: Sem chamadas de API
4. **Previsível**: Comportamento consistente

### Desvantagens
1. **Não corrige equações complexas**: Apenas padrões conhecidos
2. **Não usa contexto do PDF**: Apenas correções locais

---

## Correções Regex Implementadas

| Padrão | Correção | Exemplo |
|--------|----------|---------|
| `\gammar` | `\gamma_r` | `\gammar = 1` → `\gamma_r = 1` |
| `kgf/m³` | `kgf/m^3` | `kgf/m³` → `kgf/m^3` |
| `N/m³` | `N/m^3` | `N/m³` → `N/m^3` |
| `m³` | `m^3` | `m³` → `m^3` |

---

## Funções de API Preparadas (Desabilitadas)

As seguintes funções foram implementadas mas estão desabilitadas temporariamente:

1. **`_fix_formulas_single_call()`** - Corrige tudo em uma chamada (precisa de timeout maior)
2. **`_fix_formulas_chunked()`** - Corrige em múltiplos chunks com tasks.md
3. **`fix_formulas_via_temp_file()`** - Abordagem original com arquivos temporários

Para reabilitar:
```python
# No arquivo pdf2md_service.py, linha ~1870
# Substituir:
return fix_formulas_with_pdf_context(...)

# Por:
return _fix_formulas_chunked(...)
```

---

## Recomendações Futuras

### Opção 1: API Local (Ollama)
- Usar Ollama com modelo local (ex: llama3, mistral)
- Sem timeout de rede
- Custo de infraestrutura local

### Opção 2: API Especializada
- Usar API de correção de LaTeX específica
- Menor input (apenas fórmulas, não todo o texto)

### Opção 3: Pré-processamento
- Detectar fórmulas quebradas primeiro
- Enviar APENAS as linhas problemáticas para API
- Reduzir input drasticamente

### Opção 4: Regex Expandido
- Adicionar mais padrões de correção conhecidos
- Cobrir mais casos de uso sem API

---

## Histórico de Execuções

| Data | Abordagem | Resultado |
|------|-----------|-----------|
| 2024-03-16 | Line-by-line | API retornando vazio |
| 2024-03-16 | PDF + MD completo | Timeout 60s |
| 2024-03-16 | Chunking | Timeout + erro código |
| 2024-03-16 | Timeout 120s | Muito lento (~4min) |
| 2024-03-16 | **Regex direto** | **✅ Sucesso - 7 correções** |

---

## Conclusão

A abordagem com APIs deLLM para correção de fórmulas em PDFs grandes enfrenta desafios significativos de:
1. **Latência**: Tempo de resposta incompatível com processamento de arquivos
2. **Custo**: Input grande = custo alto
3. **Confiabilidade**: Respostas inconsistentes

A solução atual (regex direto) é mais prática para o caso de uso, sendo rápida e confiável. Para casos mais complexos, recomenda-se usar Ollama local ou enviar apenas fragmentos menores para a API.
