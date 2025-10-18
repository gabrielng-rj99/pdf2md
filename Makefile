.PHONY: help install run dev clean test lint format install-deps

help:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║              PDF2MD - Comandos Disponíveis                 ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Instalação e Setup:"
	@echo "  make install          Cria venv e instala dependências"
	@echo "  make install-deps     Instala dependências (sem criar venv)"
	@echo ""
	@echo "Desenvolvimento:"
	@echo "  make run              Executa o servidor (com reload)"
	@echo "  make dev              Alias para 'run'"
	@echo "  make clean            Remove arquivos gerados e cache"
	@echo ""
	@echo "Qualidade de Código:"
	@echo "  make lint             Verifica estilo de código (pylint)"
	@echo "  make format           Formata código com black"
	@echo ""
	@echo "Documentação:"
	@echo "  make docs             Abre documentação local"
	@echo ""
	@echo "Utilidades:"
	@echo "  make test-api         Testa upload de PDF via API"
	@echo "  make ps               Mostra processos Python rodando"
	@echo "  make kill             Mata servidor na porta 8000"
	@echo ""

install:
	@echo "📦 Criando ambiente virtual..."
	python3 -m venv .venv
	@echo "✅ Ambiente virtual criado!"
	@echo "📥 Instalando dependências..."
	. .venv/bin/activate && pip install -r requirements.txt
	@echo "✅ Dependências instaladas!"
	@echo ""
	@echo "🚀 Para iniciar o servidor, execute: make run"

install-deps:
	@echo "📥 Instalando dependências..."
	pip install -r requirements.txt
	@echo "✅ Dependências instaladas!"

run:
	@echo "🚀 Iniciando servidor..."
	python run.py

dev: run

clean:
	@echo "🧹 Limpando arquivos temporários..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ 2>/dev/null || true
	@echo "✅ Limpeza concluída!"

test-api:
	@if [ -f "aula1.pdf" ]; then \
		echo "📤 Enviando PDF para API..."; \
		curl -F "file=@aula1.pdf" http://localhost:8000/api/upload/ | jq '.'; \
	else \
		echo "❌ Arquivo aula1.pdf não encontrado"; \
	fi

lint:
	@echo "🔍 Verificando código..."
	python -m pylint app/ --disable=all --enable=E,F 2>/dev/null || echo "Instale pylint: pip install pylint"

format:
	@echo "✨ Formatando código..."
	python -m black app/ frontend/ 2>/dev/null || echo "Instale black: pip install black"

docs:
	@echo "📖 Abrindo documentação..."
	@if command -v xdg-open > /dev/null; then \
		xdg-open README.md; \
	elif command -v open > /dev/null; then \
		open README.md; \
	else \
		echo "Abra manualmente: README.md"; \
	fi

ps:
	@echo "🔍 Processos Python:"
	ps aux | grep -E "python|uvicorn" | grep -v grep

kill:
	@echo "🛑 Encerrando servidor..."
	pkill -f "uvicorn app.main:app" || pkill -f "python run.py" || echo "Nenhum servidor encontrado"
	@echo "✅ Servidor encerrado!"

.SILENT: help
