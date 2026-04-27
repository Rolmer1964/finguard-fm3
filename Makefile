SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help up down build logs ps clean generate-data batch batch-500 analyze

help:
	@echo "FinGuard Nível 2 - alvos disponíveis:"
	@echo "  make up               Sobe o serviço (build + start)"
	@echo "  make down             Para o serviço"
	@echo "  make build            Reconstrói a imagem"
	@echo "  make logs             Tail dos logs (mostra entrada/saída/tempo de cada agente)"
	@echo "  make ps               Status do container"
	@echo "  make clean            Para e remove volumes"
	@echo "  make generate-data    Gera data/synthetic_complaints.csv (~50 reclamações)"
	@echo "  make batch            Processa data/synthetic_complaints.csv via /batch"
	@echo "  make batch-500        Processa scripts/reclamacoes_bancarias_500.csv via /batch"
	@echo "  make analyze TEXT='...'  Analisa um texto avulso via /analyze"

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
