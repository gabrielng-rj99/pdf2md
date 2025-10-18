# 📄 PDF-to-Markdown-with-Images

Converta PDFs em Markdown com extração automática e inteligente de imagens. 🎯

[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green)](https://fastapi.tiangolo.com/)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-1.24.1-orange)](https://pymupdf.readthedocs.io/)
[![Tests](https://img.shields.io/badge/Tests-66%2F66%20✅-brightgreen)](https://github.com/gabrielng-rj99/pdf2md)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![Self-Host Only](https://img.shields.io/badge/Type-Self--Host%20Only-red)](#-importante---self-host-only)

## ⚠️ IMPORTANTE - Self-Host Only

**Este programa foi desenvolvido especificamente para self-host em ambientes privados** (doméstico/corporativo).

🔴 **NÃO é recomendado fazer deploy em produção pública** (internet aberta) sem implementar as melhorias de segurança listadas na seção [Roadmap Futuro](#-roadmap-futuro-segurança).

✅ **Mantenha em ambiente self-host com acesso controlado.**

---

## 🎯 O Que É?

**PDF-to-Markdown-with-Images** é uma ferramenta web que converte PDFs em Markdown mantendo:

- ✅ **Texto formatado** - Estrutura e estilo do documento
- ✅ **Imagens relevantes** - Com filtro inteligente para remover bordas/cabeçalhos
- ✅ **Referências** - Detecta "Figura 1", "Tabela 3", etc. automaticamente
- ✅ **Suporte multilíngue** - Português e inglês (extensível)
- ✅ **Arquitetura segura** - App isolado em rede privada, nginx faz proxy

### Antes vs Depois

| Antes | Depois |
|-------|--------|
| 47 imagens (93% bordas) | 3 imagens (100% relevantes) |
| Sem filtro | Filtro inteligente ativo |
| Sem testes | **66 testes passando** ✅ |
| Sem isolamento | **Redes isoladas** ✅ |

---

## 🚀 Quick Start

### Prerequisitos

- **Docker** e **Docker Compose** (recomendado)
- **Python 3.8+** (para desenvolvimento sem Docker)
- **Git**

### Com Docker (Recomendado)

```bash
# 1. Clone o repositório
git clone https://github.com/gabrielng-rj99/pdf2md.git
cd PDF-to-Markdown-with-Images

# 2. Configure o DNS/hosts (IMPORTANTE!)
# Adicione à sua máquina para resolver o domínio:
# Linux/macOS: sudo nano /etc/hosts
# Windows: C:\Windows\System32\drivers\etc\hosts
# Adicione a linha:
# 127.0.0.1 pdf2md.home.arpa

# 3. Entre no diretório deploy
cd deploy

# 4. Configure as variáveis (edite o arquivo .env existente)
nano .env  # ou use seu editor favorito
# Revise TODOS os parâmetros em .env, especialmente DOMAIN

# 5. Inicialize (cria rede, certificados, build e inicia)
bash init.sh up

# 6. Acesse
https://pdf2md.home.arpa  (com certificado self-signed)
```

### Sem Docker (Desenvolvimento Local)

```bash
# 1. Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou
.venv\Scripts\activate  # Windows

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Rodar servidor
python run.py

# 4. Acesse
http://localhost:8000
```

---

## 📚 Documentação

### Para Usuários

| Guia | Conteúdo |
|------|----------|
| **Este README.md** | Visão geral, features, arquitetura, deployment com Docker, roadmap |
| **deploy/.env** | Todos os parâmetros de deployment (edite conforme sua ambiente) |
| **deploy/QUICK_START.md** | 2 minutos para colocar em produção |

### Para Desenvolvedores

| Guia | Conteúdo |
|------|----------|
| **docs/README.md** | Setup local, como adicionar features, testes, arquitetura Clean |
| **config.ini** | Configurações da aplicação (upload, filtros, servidor) |

### Referência Rápida

- **Deployment**: `cd deploy && bash init.sh up`
- **Desenvolvimento**: `python run.py` ou `pytest tests/`
- **Configuração**: `config.ini` (app) + `deploy/.env` (docker)

---

## 🔧 Arquitetura

### Componentes

```
┌─────────────────────────────────────────────┐
│             HOST (Seu computador)           │
├─────────────────────────────────────────────┤
│                                              │
│  Port 80 (HTTP)  │  Port 443 (HTTPS)        │
│         │                │                  │
└─────────│────────────────│──────────────────┘
          │                │
          └────────┬───────┘
                   │
          ┌────────▼─────────┐
          │  Nginx Container │
          │ (Reverse Proxy)  │
          └────────┬─────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        │  Network:           │
        │  app_internal       │
        │  (Privada)          │
        │                     │
  ┌─────▼──────┐   ┌─────────▼──────┐
  │    App     │   │     Nginx      │
  │  :8000     │   │    :172.18...  │
  │ (Bloqueado)│   │                │
  └────────────┘   └────────────────┘
```

### Redes Docker

1. **app_internal** (172.18.0.0/24) - Privada
   - App: 172.18.0.200:8000 (BLOQUEADO do host)
   - Nginx: 172.18.0.201
   - ✅ Apenas nginx acessa o app

2. **app_external** (172.19.0.0/24) - Pública
   - Nginx: 172.19.0.100
   - ✅ Expõe portas 80/443 ao host

### Fluxo

```
1. Cliente (HTTP/HTTPS)
   ↓
2. Nginx (portas 80/443)
   ↓
3. App (port 8000 - rede privada, bloqueado)
   ↓
4. Processamento PDF
   ↓
5. Saída: Markdown + Imagens
```

---

## 📊 Recursos Principais

### 🎨 Frontend Interativo

- ✅ Upload com **clique** ou **drag-and-drop**
- ✅ Validação de arquivo e tamanho (500MB)
- ✅ Feedback visual em tempo real
- ✅ Download direto do Markdown
- ✅ Responsivo para mobile
- ✅ Dark mode ready

### 🔧 API REST

```bash
# Health check
curl http://localhost:8000/api/health/

# Upload PDF
curl -F "file=@documento.pdf" http://localhost:8000/api/upload/

# Download Markdown
curl http://localhost:8000/api/download/documento.md
```

### 🧠 Filtro Inteligente de Imagens

#### Detecta e Remove:
- 📌 **Cabeçalhos** (primeiros 10% da página)
- 📌 **Rodapés** (últimos 10% da página)
- 📌 **Margens laterais** (imagens < 50px)
- 📌 **Artefatos** (< 3000 pixels²)

#### Mantém:
- ✅ Imagens no corpo do texto
- ✅ Imagens referenciadas ("Figura 1", "Tabela 3")
- ✅ Imagens com tamanho significativo

#### Suporta:
- 🌍 **Português**: Figura, Tabela, Imagem, Gráfico
- 🌍 **English**: Figure, Table, Image, Chart

### ⚙️ Configuração Centralizada

```ini
[UPLOAD]
max_file_size_mb = 500

[IMAGE_FILTER]
header_margin_percent = 0.10
footer_margin_percent = 0.10
min_image_area = 3000
```

---

## 📋 Limitações Conhecidas

### Edge Case: PDFs com Mesmo Nome

**Problema**: Se você enviar dois PDFs com o mesmo nome (de pastas diferentes), as imagens geradas terão o mesmo nome e se sobrescreverão.

```
Upload 1: Pasta A/aula1.pdf  → gera: aula1_page_001.jpg
Upload 2: Pasta B/aula1.pdf  → sobrescreve: aula1_page_001.jpg ❌
```

**Workaround Temporal**: Renomear PDFs para nomes únicos:
```
✅ Correto: aula1_A.pdf, aula1_B.pdf
✅ Correto: 2024_01_aula1.pdf, 2024_02_aula1.pdf
```

**Solução Permanente**: Implementada em futuro patch (usar hash/UUID para nomes únicos).

---

## 🧪 Testes

✅ **219 testes passando** | **73% cobertura** | ~9 segundos

```bash
# Rodar testes
pytest tests/unit tests/integration -v

# Com cobertura
pytest tests/unit tests/integration --cov=app --cov-report=html
```

**Veja [TESTING.md](TESTING.md) para guia completo.**

---

## 🏗️ Arquitetura de Código

### Clean Architecture

```
app/
├── main.py                    # API FastAPI
├── services/
│   └── pdf2md_service.py     # Processamento de PDF
├── core/
│   └── formatter.py          # Formatação
└── utils/
    ├── image_filter.py       # Filtro de imagens (244 linhas)
    └── helpers.py            # Utilitários

frontend/
├── index.html                # Interface web
├── script.js                 # Upload + drag-and-drop
└── style.css                 # Estilos responsivos

deploy/
├── init.sh                   # Script de inicialização
├── docker-compose.yml        # 2 redes isoladas
├── Dockerfile                # Imagem da app
└── nginx/conf.d/default.conf # Configuração proxy
```

### Fluxo de Processamento

```
1. Frontend
   ↓
   Upload PDF

2. API (/api/upload/)
   ↓
   Validação

3. PDF Service
   ↓
   PyMuPDF extraction

4. Image Filter
   ↓
   Análise + Filtragem

5. Saída
   ↓
   ✅ Markdown + Imagens
```

---

## 🔒 Segurança

### Implementado Atualmente (Self-Host)

✅ **Isolamento de Rede**
- App em rede privada (172.18.0.0/24)
- App NOT exposto ao host
- Apenas nginx acessa o app

✅ **Proxy Reverso**
- Nginx faz bridge entre redes
- Única entrada: portas 80/443

✅ **HTTPS/TLS**
- Certificados self-signed (inclusos)
- Let's Encrypt ready (via nginx-companion)

### Não Implementado (Futuro Patch)

⚠️ **Autenticação de Usuário** - Futuro patch
⚠️ **Sandbox de Processamento** - Futuro patch
⚠️ **Proteção contra PDFs Maliciosos** - Futuro patch
⚠️ **Criptografia de Dados em Repouso** - Futuro patch
⚠️ **Compliance (GDPR, Auditoria)** - Futuro patch

---

## 📦 Dependências

### Produção

```
fastapi==0.109.0                  # Web framework
uvicorn[standard]==0.27.0         # ASGI server
pymupdf==1.24.1                   # Processamento PDF
python-multipart==0.0.6           # Upload multipart
httpx==0.25.2                     # HTTP client
Pillow==11.3.0                    # Processamento de imagens
```

### Testes

```
pytest==7.4.3                     # Test framework
pytest-cov==4.1.0                 # Coverage
pytest-asyncio==0.21.1            # Async support
```

### Desenvolvimento

```
black==23.12.0                    # Code formatter
flake8==6.1.0                     # Linter
```

### Docker

```
Python 3.11 (slim)
Nginx (stable)
```

---

## 🔄 Deploy com Docker

### Variáveis de Ambiente (.env)

**⚠️ TODOS os parâmetros DEVEM estar no arquivo `.env`**. Edite `deploy/.env` conforme sua ambiente.

#### Domínio e Certificados

```env
# Domínio principal (configure também em /etc/hosts ou DNS)
DOMAIN=pdf2md.home.arpa
DOMAIN_ALIASES=

# Certificados SSL/TLS
CERT_DIR=./certs
CERT_CRT=pdf2md.home.arpa.crt
CERT_KEY=pdf2md.home.arpa.key

# Let's Encrypt (apenas para domínio público)
LETSENCRYPT=false
LETSENCRYPT_EMAIL=admin@home.arpa
```

#### Rede Interna (App + Nginx)

```env
# Rede interna de comunicação (app isolada nesta rede)
DOCKER_NETWORK_NAME=pdf2md_net
NETWORK_SUBNET=172.18.0.0/24
NETWORK_GATEWAY=172.18.0.1

# IPs dos containers na rede interna
APP_INTERNAL_IP=172.18.0.200
APP_INTERNAL_PORT=8000
NGINX_INTERNAL_IP=172.18.0.201
```

#### Rede Externa (Opcional - Multi-Host)

```env
# Para cenários multi-host (deixar como false para self-hosted)
USE_EXTERNAL_NETWORK=false
EXTERNAL_NETWORK_NAME=
```

#### Exposição de Portas (Host Binding)

```env
# CUIDADO: Expor portas torna a aplicação acessível de fora
# Para self-hosted em rede privada, manter como false

EXPOSE_HTTP=false      # HTTP porta 80
EXPOSE_HTTPS=false     # HTTPS porta 443
HOST_BIND_IP=          # IP do host (vazio = qualquer interface)
EXPOSE_HTTP_PORT=80
EXPOSE_HTTPS_PORT=443
```

#### Limpeza Automática

```env
# Remover rede Docker ao fazer "init.sh down"
REMOVE_NETWORK_ON_DOWN=true

# Remover certificados gerados ao fazer "init.sh down"
# false = mantém certificados (recomendado)
# true = apaga certs (apenas desenvolvimento)
REMOVE_CERTS_ON_DOWN=false
```

#### Configuração da Aplicação

```env
# Workers Gunicorn (processamento paralelo)
# Fórmula recomendada: (2 * CPU_cores) + 1
GUNICORN_WORKERS=4
```

**Para referência completa com todas as opções, veja `deploy/.env`.**
</parameter>


### Comandos

```bash
# Inicializar (cria rede, certificados, build, start)
cd deploy
bash init.sh up

# Parar
bash init.sh down

# Só gerar certificados
bash init.sh certs

# Só criar rede
bash init.sh network

# Ver ajuda
bash init.sh help
```

### Verificar Status

```bash
# Ver containers
docker ps

# Ver logs
docker logs extract-pdf
docker logs extract-pdf-nginx

# Testar conectividade
curl http://localhost/
curl -k https://localhost/
```

---

## 🚨 Roadmap Futuro (Segurança)

### Phase 1 - Crítico (Q1)

- [ ] Autenticação robusta (OAuth2, SAML, LDAP)
- [ ] Isolamento de processamento (sandbox por upload)
- [ ] Validação de PDFs + ClamAV
- [ ] Colisão de nomes resolvida (hash/UUID)

### Phase 2 - Importante (Q2)

- [ ] Criptografia em repouso (AES-256)
- [ ] Cache de resultados
- [ ] Logs estruturados
- [ ] Banco de dados

### Phase 3 - Bom ter (Q3)

- [ ] Processamento assíncrono (Celery)
- [ ] Multi-instância + load balancer
- [ ] Monitoramento (Prometheus)
- [ ] Alertas

### Phase 4 - Nice to have (Q4+)

- [ ] Compliance (GDPR)
- [ ] Integração com 3os
- [ ] OCR melhorado
- [ ] Machine Learning

**Status**: Estas mudanças estão agendadas para **futuro PATCH MAJOR**. Até lá, mantenha em **self-host com acesso controlado**.

Para detalhes técnicos e código de exemplo, veja `FUTURE_IMPROVEMENTS.md`.

---

## 🐛 Troubleshooting

### DNS / Acesso

**Problema**: `curl: (6) Could not resolve host` ou navegador não encontra `pdf2md.home.arpa`
```bash
# Solução 1: Verificar /etc/hosts (Linux/macOS)
cat /etc/hosts | grep pdf2md

# Se não estiver, adicionar:
sudo nano /etc/hosts
# Adicione a linha:
# 127.0.0.1 pdf2md.home.arpa

# Solução 2: Windows (C:\Windows\System32\drivers\etc\hosts)
# Adicione:
# 127.0.0.1 pdf2md.home.arpa

# Solução 3: Usar IP direto (temporário)
curl -k https://192.168.1.100 -H "Host: pdf2md.home.arpa"
```

**Problema**: `curl: (60) SSL certificate problem`
```bash
# Esperado com certificados auto-assinados
# Solução: Usar -k para ignorar validação (apenas local!)
curl -k https://pdf2md.home.arpa/

# Ou importar certificado no navegador:
# Certificado está em: deploy/certs/pdf2md.home.arpa.crt
```

### Docker

**Problema**: Nginx não inicia
```bash
# Solução: Verificar logs
docker logs extract-pdf-nginx

# Se erro de "map directive": Verifique nginx/conf.d/default.conf
# A diretiva map deve estar fora do bloco server (no contexto http)
```

**Problema**: Porta 80/443 já em uso
```bash
# Solução: Liberar a porta
lsof -i :80   # Verificar o que está usando
sudo kill -9 <PID>

# Ou usar porta diferente no .env:
EXPOSE_HTTP_PORT=8080
EXPOSE_HTTPS_PORT=8443
```

**Problema**: Certificados não funcionam
```bash
# Solução: Regenerar
cd deploy
bash init.sh clean-certs
bash init.sh certs
docker compose up -d nginx

# Nota: Se REMOVE_CERTS_ON_DOWN=true, certs são deletados ao fazer down
# Para manter certificados: REMOVE_CERTS_ON_DOWN=false
```

**Problema**: `init.sh down` deletou meus certificados
```bash
# Se você tinha REMOVE_CERTS_ON_DOWN=true
# Solução 1: Regenerar (se ainda dentro da sessão)
bash init.sh certs

# Solução 2: Definir REMOVE_CERTS_ON_DOWN=false e manter backup
# Adicione ao .env:
REMOVE_CERTS_ON_DOWN=false

# Para não deletar certs em futuras execuções
```

### Aplicação

**Problema**: Acesso recusado / 502 Bad Gateway
```bash
# Solução: Verificar se app está rodando
docker ps | grep extract-pdf

# Ver logs da aplicação
docker logs extract-pdf

# App pode estar travada; reiniciar:
docker restart extract-pdf
```

**Problema**: ModuleNotFoundError ao rodar tests
```bash
# Solução: Certifique-se do diretório
cd PDF-to-Markdown-with-Images
python3 run_tests.py
```

**Problema**: Upload falha / timeout
```bash
# Solução: Verificar se servidor está rodando
docker exec extract-pdf curl http://127.0.0.1:8000/api/health/

# Se falhar, verificar logs
docker logs extract-pdf

# Aumentar timeout em .env (se necessário)
# Ver config.ini para limites de arquivo
cat config.ini | grep max_file_size
```

**Problema**: Testes falhando com Pillow
```bash
# Solução: Usar Python 3.11/3.12 (não 3.13)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 📋 Features Checklist

### ✅ Concluído

- [x] Upload de PDF (clique e drag-and-drop)
- [x] Conversão para Markdown
- [x] Extração de imagens
- [x] Filtro inteligente
- [x] Detecção de referências
- [x] Suporte multilíngue
- [x] Validação de arquivo
- [x] Limitador de tamanho
- [x] Configuração centralizada
- [x] Health check API
- [x] Download de Markdown
- [x] CORS configurado
- [x] 47 testes unitários
- [x] 19 testes de integração
- [x] Documentação completa
- [x] Frontend responsivo
- [x] Tratamento de erros
- [x] Docker + nginx + HTTPS
- [x] Redes isoladas (segurança self-host)
- [x] Init script (certificados, redes, build)

### 📋 Planejado

- [ ] Autenticação (futuro patch)
- [ ] Sandbox de processamento (futuro patch)
- [ ] Proteção contra PDFs maliciosos (futuro patch)
- [ ] Colisão de nomes automática (futuro patch)
- [ ] Testes E2E
- [ ] Upload múltiplo
- [ ] Histórico de conversões
- [ ] Banco de dados
- [ ] Cache de resultados
- [ ] Machine Learning para filtro

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. **Fork** o repositório
2. **Crie uma branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit suas mudanças** (`git commit -m 'Add AmazingFeature'`)
4. **Push para a branch** (`git push origin feature/AmazingFeature`)
5. **Abra um Pull Request**

### Padrões de Código

- Siga [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints
- Docstrings em português
- Testes para cada funcionalidade
- Cobertura > 80%

### Desenvolvimento Local

```bash
# Clonar e entrar
git clone https://github.com/gabrielng-rj99/pdf2md.git
cd PDF-to-Markdown-with-Images

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Rodar
python run.py

# Testar
python run_tests.py --coverage

# Code style
black app/ tests/
flake8 app/ tests/
```

---

## 📄 Licença

Este projeto está licenciado sob a **Licença MIT** - veja [LICENSE](LICENSE) para detalhes.

---

## 📞 Suporte

Tem dúvidas?

- 📖 Consulte `deploy/QUICK_START.md` (uso)
- 📖 Consulte `deploy/TESTES.md` (detalhes técnicos)
- 📖 Consulte `docs/README_CLEAN.md` (arquitetura)
- 🐛 Abra uma [issue](https://github.com/gabrielng-rj99/pdf2md/issues)

---

## 🎉 Status

### ✅ SELF-HOST READY

- ✅ Código testado e validado (66 testes)
- ✅ Docker + nginx + HTTPS configurado
- ✅ Redes isoladas (segurança)
- ✅ Documentação completa
- ✅ Pronto para deployment interno

### ⚠️ NÃO para Produção Pública

- Sem autenticação de usuário
- Sem sandbox de processamento
- Sem proteção contra PDFs maliciosos
- Aguarde futuro patch major

---

## 📊 Informações do Projeto

| Item | Valor |
|------|-------|
| **Versão** | 1.0.0 |
| **Tipo** | Self-Host |
| **Status** | Estável ✅ |
| **Testes** | 66/66 ✅ |
| **Python** | 3.8+ |
| **FastAPI** | 0.109.0 |
| **PyMuPDF** | 1.24.1 |
| **Docker** | Sim ✅ |
| **HTTPS** | Sim ✅ |
| **Redes Isoladas** | Sim ✅ |
| **Último Update** | Outubro 2024 |

---

**Desenvolvido com ❤️ usando Python, FastAPI, Docker e testes automatizados**

**Mantenha em self-host com acesso controlado. Não exponha na internet pública.** 🔒