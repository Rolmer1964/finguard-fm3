SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help up down build logs ps clean generate-data batch batch-500 analyze rag-ingest rag-status adr

help:
	@echo "FinGuard Nível 3 - alvos disponíveis:"
	@echo "  make up               Sobe o serviço (build + start)"
	@echo "  make down             Para o serviço"
	@echo "  make build            Reconstrói a imagem"
	@echo "  make logs             Tail dos logs (mostra entrada/saída/tempo de cada nó)"
	@echo "  make ps               Status do container"
	@echo "  make clean            Para e remove volumes"
	@echo "  make generate-data    Gera data/synthetic_complaints.csv (~50 reclamações)"
	@echo "  make batch            Processa data/synthetic_complaints.csv via /batch"
	@echo "  make batch-500        Processa scripts/reclamacoes_bancarias_500.csv via /batch"
	@echo "  make analyze TEXT='...'  Analisa um texto avulso via /analyze"
	@echo "  make rag-ingest       Sincroniza assets/docs/ com o índice RAG (incremental por hash)"
	@echo "  make rag-status       Mostra resumo do índice RAG (manifest)"
	@echo "  make adr              Salva o ADR atual em docs/adr.html"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

clean:
	$(COMPOSE) down -v

generate-data:
	python scripts/generate_synthetic.py

batch:
	@curl -s -F "file=@data/synthetic_complaints.csv" http://localhost:8000/batch | python -m json.tool

batch-500:
	@curl -s -F "file=@scripts/reclamacoes_bancarias_500.csv" http://localhost:8000/batch | python -m json.tool

analyze:
	@curl -s -X POST http://localhost:8000/analyze \
	  -H "Content-Type: application/json" \
	  -d "{\"text\": \"$(TEXT)\"}" | python -m json.tool

rag-ingest:
	$(COMPOSE) exec app python -m src.rag.ingest

rag-status:
	@if [ -f assets/index/manifest.json ]; then \
		python -c "import json; m=json.load(open('assets/index/manifest.json',encoding='utf-8')); print(f\"vetores: {m['next_id']}\\narquivos: {len(m['files'])}\\natualizado: {m.get('updated_at')}\\n\"); [print(f'  {p} ({len(v[\"chunk_ids\"])} chunks, sha={v[\"hash\"][:8]})') for p,v in m['files'].items()]"; \
	else \
		echo "Nenhum índice ainda. Rode: make rag-ingest"; \
	fi

adr:
	@curl -s -X POST http://localhost:8000/adr/save | python -m json.tool
