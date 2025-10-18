# 📄 PDF-to-Markdown-with-Images

Converta PDFs em Markdown com extração automática e inteligente de imagens. 🎯

[![Python 3.13.7](https://img.shields.io/badge/Python-3.13.7-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green)](https://fastapi.tiangolo.com/)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-1.24.1-orange)](https://pymupdf.readthedocs.io/)
[![Tests](https://img.shields.io/badge/Tests-210%2B%20✅-brightgreen)](#-testes)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![Self-Host Only](https://img.shields.io/badge/Type-Self--Host%20Only-red)](#-importante---self-host-only)

## ⚠️ IMPORTANTE - Self-Host Only

**Este programa foi desenvolvido especificamente para self-host em ambientes privados** (doméstico/corporativo).

🔴 **NÃO é recomendado fazer deploy em produção pública** sem implementar autenticação, rate limiting e outras medidas de segurança.

✅ **Mantenha em ambiente self-host com acesso controlado.**

---

## 🎯 O Que É?

**PDF-to-Markdown-with-Images** é uma ferramenta web que converte PDFs em Markdown mantendo:

- ✅ **Texto formatado** - Estrutura e estilo do documento
- ✅ **Imagens relevantes** - Com filtro inteligente para remover bordas/cabeçalhos
- ✅ **Referências automáticas** - Detecta "Figura 1", "Tabela 3", etc.
- ✅ **Suporte multilíngue** - Português e inglês (extensível)
- ✅ **Arquitetura segura** - App isolado em rede privada, nginx faz proxy

---

## 🚀 Quick Start

### Prerequisitos

- **Docker** e **Docker Compose** (recomendado)
- **Python 3.13.7** (para desenvolvimento sem Docker)
- **Git**

### Com Docker (Recomendado)

```bash
# 1. Clone o repositório
git clone https://github.com/gabrielng-rj99/pdf2md.git
cd PDF-to-Markdown-with-Images

# 2. Configure o DNS/hosts
# Linux/macOS: sudo nano /etc/hosts
# Windows: C:\Windows\System32\drivers\etc\hosts
# Adicione:
# 127.0.0.1 pdf2md.home.arpa

# 3. Entre no diretório deploy e inicialize
cd deploy
bash init.sh up

# 4. Acesse
# https://pdf2md.home.arpa (com certificado self-signed)
```

### Sem Docker (Desenvolvimento Local)

```bash
# 1. Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS ou .venv\Scripts\activate (Windows)

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Rodar servidor
python run.py

# 4. Acesse em http://localhost:8000
```

---

## 📚 Documentação

- **[TESTING.md](docs/TESTING.md)** - Guia completo de testes e cobertura
- **[TEST_COVERAGE_REPORT.md](docs/TEST_COVERAGE_REPORT.md)** - Relatório detalhado de cobertura
- **[TEST_FILES_CREATED.md](docs/TEST_FILES_CREATED.md)** - Lista completa de testes criados

---

## 🏗️ Arquitetura

### Estrutura de Pastas

```
app/
├── main.py                    # API FastAPI
├── services/
│   └── pdf2md_service.py     # Processamento de PDF
├── core/
│   └── formatter.py          # Formatação Markdown
└── utils/
    ├── image_filter.py       # Filtro inteligente de imagens
    └── helpers.py            # Utilitários

frontend/
├── index.html                # Interface web
├── script.js                 # Upload + drag-and-drop
└── style.css                 # Estilos responsivos

deploy/
├── init.sh                   # Script de inicialização
├── docker-compose.yml        # Orquestração com 2 redes isoladas
├── Dockerfile                # Imagem da aplicação
└── nginx/conf.d/default.conf # Configuração proxy reverso
```

### Fluxo de Processamento

```
Frontend Upload PDF
         ↓
API /api/upload/ (validação)
         ↓
PDF Service (PyMuPDF extraction)
         ↓
Image Filter (análise + filtragem)
         ↓
Saída: Markdown + Imagens (ZIP)
```

### Redes Docker

- **rede privada (172.18.0.0/24)**: App isolado, não exposto ao host
- **Nginx proxy**: Faz bridge entre redes, aceita conexões HTTPS do host
- **Certificados**: Gerados por `deploy/init.sh`, auto-assinados para self-host

---

## 🧪 Testes

✅ **210+ testes passando** | **~85% cobertura** | ~9 segundos

```bash
# Rodar testes
pytest tests/unit tests/integration -v

# Com cobertura
pytest tests/unit tests/integration --cov=app --cov-report=html

# Ver relatório (após gerar HTML)
xdg-open htmlcov/index.html  # Linux
open htmlcov/index.html      # macOS
```

---

## 📦 Dependências

### Produção
- `FastAPI==0.109.0` - Framework web
- `PyMuPDF==1.24.1` - Extração de PDF
- `Pillow==10.1.0` - Processamento de imagens
- `python-multipart==0.0.6` - Upload de arquivos
- `gunicorn==21.2.0` - Servidor WSGI

### Testes
- `pytest==7.4.4` - Framework de testes
- `pytest-cov==4.1.0` - Cobertura de testes

### Desenvolvimento
- `black==23.12.1` - Formatação de código
- `flake8==6.1.0` - Lint

---

## 🔧 Deploy com Docker

### Configuração Básica (.env)

O arquivo `deploy/.env` contém todas as variáveis necessárias:

```env
# Domínio e certificados
DOMAIN=pdf2md.home.arpa
CERT_CRT=pdf2md.home.arpa.crt
CERT_KEY=pdf2md.home.arpa.key

# Rede interna
DOCKER_NETWORK_NAME=pdf2md_net
NETWORK_SUBNET=172.18.0.0/24
APP_INTERNAL_IP=172.18.0.200
APP_INTERNAL_PORT=8000
NGINX_INTERNAL_IP=172.18.0.201

# Workers (fórmula: (2 * CPU cores) + 1)
GUNICORN_WORKERS=4
```

### Comandos

```bash
cd deploy

# Inicializar (cria rede, certificados, build, inicia containers)
bash init.sh up

# Parar
bash init.sh down

# Gerar apenas certificados
bash init.sh certs

# Ver ajuda
bash init.sh help

# Verificar status
docker ps
```

---

## 🔒 Segurança Implementada

- ✅ **Isolamento de rede** - App em rede privada (172.18.0.0/24)
- ✅ **Proxy reverso** - Nginx faz bridge entre redes
- ✅ **HTTPS com certificados** - Auto-assinados para self-host
- ✅ **Validação de entrada** - Tamanho máximo de arquivo: 500 MB
- ✅ **Sanitização de nomes** - Prevenção de path traversal

**Nota**: Para produção pública, adicione autenticação, rate limiting e WAF.

---

## 📋 Limitações Conhecidas

### PDFs com Mesmo Nome

Se enviar dois PDFs com o mesmo nome (de pastas diferentes), as imagens geradas podem se sobrescrever. **Workaround**: Renomear PDFs para nomes únicos (`aula1_A.pdf`, `aula1_B.pdf`, etc).

---

## 🐛 Troubleshooting

### Problema: "DNS_PROBE_FINISHED_NXDOMAIN"
**Solução**: Adicione `127.0.0.1 pdf2md.home.arpa` em `/etc/hosts` (Linux/macOS) ou `C:\Windows\System32\drivers\etc\hosts` (Windows).

### Problema: Certificado Inválido
**Solução**: É esperado para self-host com certificados auto-assinados. Clique em "Prosseguir mesmo assim" no navegador ou confie no certificado.

### Problema: Container não inicia
**Solução**: Verifique se a porta 443 já está em uso: `sudo lsof -i :443` (Linux/macOS).

### Problema: Upload falha
**Solução**: Verifique tamanho do arquivo (máx 500 MB) e se há espaço em disco.

---

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch: `git checkout -b feature/sua-feature`
3. Commit com mensagens descritivas
4. Push e abra um Pull Request

### Padrões de Código

- Use `black` para formatação: `black app/ tests/`
- Use `flake8` para lint: `flake8 app/ tests/`
- Cobertura mínima: 80%

---

## 📄 Licença

Este projeto é licenciado sob a [MIT License](LICENSE).

---

## 📞 Suporte

Encontrou um bug ou tem uma sugestão? Abra uma [issue](https://github.com/gabrielng-rj99/pdf2md/issues).

---

## ✅ Status

- **Self-Host**: ✅ Pronto para uso
- **Testes**: ✅ 210+ testes passando
- **Cobertura**: ✅ ~85%
- **Documentação**: ✅ Completa