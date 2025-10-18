# 📚 Documentação - PDF-to-Markdown-with-Images

Bem-vindo à documentação. Este diretório centraliza a documentação auxiliar do projeto.

---

## 📋 Índice

### Para Começar Rápido
- **[01_QUICK_START.md](01_QUICK_START.md)** — Deploy em 2 minutos

### Para Desenvolvedores
- **[02_ARCHITECTURE.md](02_ARCHITECTURE.md)** — Arquitetura técnica, setup local, features

### Para Operadores
- **[../README.md](../README.md)** — Documentação principal
  - Visão geral, features, deployment, troubleshooting, roadmap

### Referência
- **[../config.ini](../config.ini)** — Configurações da aplicação
- **[../deploy/.env](../deploy/.env)** — Variáveis de deployment

---

## 🚀 Começar em 3 Passos

```bash
# 1. Clone
git clone https://github.com/gabrielng-rj99/pdf2md.git
cd PDF-to-Markdown-with-Images/deploy

# 2. Configure DNS
# /etc/hosts: 172.19.0.100 pdf2md.home.arpa

# 3. Inicie
nano .env
bash init.sh up
```

Acesse: https://pdf2md.home.arpa

---

## 📚 Onde Encontrar...

| Preciso... | Veja... |
|-----------|---------|
| **Deploy rápido** | [01_QUICK_START.md](01_QUICK_START.md) |
| **Arquitetura & Dev** | [02_ARCHITECTURE.md](02_ARCHITECTURE.md) |
| **Testes** | [../TESTING.md](../TESTING.md) |
| **Visão geral** | [../README.md](../README.md) |
| **Configuração** | [../config.ini](../config.ini) |
| **Deploy setup** | [../deploy/.env](../deploy/.env) |
| **Troubleshooting** | [../README.md](../README.md#-troubleshooting) |

---

## 📁 Estrutura

```
docs/
├── README.md              ← Você está aqui
├── 01_QUICK_START.md      ← Deploy rápido
└── 02_ARCHITECTURE.md     ← Arquitetura & dev

../
├── README.md              ← Documentação principal
├── TESTING.md             ← Guia único de testes
├── config.ini             ← Configurações
├── requirements.txt       ← Dependências
├── deploy/                ← Docker & deployment
├── app/                   ← Código-fonte
├── tests/                 ← Suite de testes (219 testes)
└── output/                ← Arquivos processados
```

---

## ✅ Checklist de Setup

- [ ] Leu [../README.md](../README.md)
- [ ] DNS/hosts configurado
- [ ] Editou [../deploy/.env](../deploy/.env)
- [ ] Executou `bash init.sh up`
- [ ] Acessou https://pdf2md.home.arpa
- [ ] Testou upload de PDF

---

## 📝 Próximos Passos

- Novo desenvolvedor? → [02_ARCHITECTURE.md](02_ARCHITECTURE.md)
- Deploy em produção? → [../README.md](../README.md)
- Rodar testes? → [../TESTING.md](../TESTING.md)

---

**Status:** ✅ Pronto para usar
