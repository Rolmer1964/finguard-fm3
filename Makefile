SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help up down build logs ps restart clean security-scan generate-data seed-complaints

help:
	@echo "FinGuard - alvos disponíveis:"
	@echo "  make up               Sobe toda a stack em background"
	@echo "  make down             Para a stack"
	@echo "  make build            Reconstrói as imagens"
	@echo "  make logs             Tail dos logs"
	@echo "  make ps               Status dos containers"
	@echo "  make restart          Restart de todos os serviços"
	@echo "  make clean            Para e remove volumes (apaga dados!)"
	@echo "  make generate-data    Gera dataset sintético em data/"
	@echo "  make seed-complaints  Envia o dataset para o backend"
	@echo "  make security-scan    Roda Bandit/Semgrep/pip-audit/npm-audit/Trivy"

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

restart:
	$(COMPOSE) restart

clean:
	$(COMPOSE) down -v

generate-data:
	python scripts/generate_synthetic.py

seed-complaints:
	python scripts/seed_complaints.py

security-scan:
	bash infra/security/scan.sh
