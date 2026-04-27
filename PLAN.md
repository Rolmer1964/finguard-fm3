# Plano: FinGuard — Backend microsserviços (Python) + Frontend (React/TS) + Docker

## Context

O desafio Future Minds 3 ("FinGuard") pede um sistema que recebe reclamações de clientes de uma instituição financeira em texto livre e devolve uma análise estruturada (categoria, produto, sentimento, urgência, resumo, parecer de risco e relatório gerencial). O usuário escolheu atacar o **Nível 3 (Avançado)**, que exige guardrails de entrada/saída via **AWS Bedrock**, ADR navegável em HTML e justificativa de custos.

A entrega será uma aplicação web composta por:
- Backend Python em **microsserviços reais** (containers separados) atrás de um API Gateway, com autenticação JWT e admin inicial provisionado via `.env`.
- Frontend em **React + Vite (TypeScript)** com tela de login e dashboards de análise.
- Toda a stack subindo via `docker compose`.
- Verificação de vulnerabilidades local via script após o setup inicial.

Observação sobre a documentação: o `regras.md` (Karpathy) pede simplicidade e mudanças cirúrgicas. A escolha do usuário por microsserviços reais aumenta a complexidade naturalmente, então o plano mantém cada serviço enxuto (≤ ~6 arquivos) e não introduz abstrações além das exigidas pela separação de processos. Sobre o `documentacao.md`: o único requisito de linguagem fixa é **HTML como formato de saída** do relatório de análises e do ADR — isso é um *artefato gerado*, não a tecnologia do front. React/TS está de acordo com o desafio.

---

## Arquitetura

```
┌──────────────┐   HTTPS    ┌─────────────────┐
│  React+Vite  │ ─────────► │  API Gateway    │  porta 8000 (única exposta)
│  (nginx)     │            │  (FastAPI+JWT)  │
└──────────────┘            └────────┬────────┘
   porta 3000                        │ rede interna
                       ┌─────────────┼─────────────┬───────────────┐
                       ▼             ▼             ▼               ▼
                ┌───────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────┐
                │  auth     │ │  complaint   │ │   agent-    │ │ report   │
                │  service  │ │  service     │ │ orchestrator│ │ service  │
                │ (FastAPI) │ │  (FastAPI)   │ │ (LangGraph) │ │ (FastAPI)│
                └─────┬─────┘ └──────┬───────┘ └──────┬──────┘ └────┬─────┘
                      │              │                │             │
                      └──────────────┴────────┬───────┴─────────────┘
                                              ▼
                                      ┌───────────────┐
                                      │  PostgreSQL   │  schemas: auth, complaints, reports
                                      └───────────────┘
                                              │
                                              ▼
                                      ┌───────────────┐
                                      │ AWS Bedrock   │  modelos + guardrails
                                      └───────────────┘
```

**Por que essa divisão:** cada serviço tem responsabilidade única (auth, persistência de reclamações, orquestração agêntica, geração de relatórios) e pode evoluir/escalar independentemente. O Gateway é o único ponto exposto, valida o JWT e propaga `X-User-Id` aos serviços internos via rede privada do compose.

**Modelos Bedrock (justificativa de custos para o ADR):**
- Triagem: `anthropic.claude-3-haiku` (barato, classificação rápida).
- Risco/Conformidade: `anthropic.claude-sonnet-4-6` (melhor raciocínio para detectar fraude/LGPD).
- Relatório: `anthropic.claude-3-haiku` (consolidação tem prompt curto).

---

## Estrutura de diretórios

```
MARCELO/
├── docker-compose.yml
├── .env.example                     # ADMIN_EMAIL, ADMIN_PASSWORD, JWT_SECRET, AWS_*, BEDROCK_GUARDRAIL_ID
├── Makefile                         # up, down, security-scan, seed, generate-data
├── README.md                        # como subir e operar
├── data/
│   ├── synthetic_complaints.csv     # gerado por script
│   ├── politica_interna.md          # base RAG (texto fictício de política)
│   └── reports/                     # saídas HTML montadas em volume
├── docs/
│   └── adr.html                     # gerado pelo report-service
├── infra/
│   ├── postgres/init.sql            # cria schemas auth/complaints/reports
│   └── security/
│       ├── scan.sh                  # roda Bandit, Semgrep, pip-audit, npm audit, Trivy
│       └── README.md
├── scripts/
│   └── generate_synthetic.py        # gera ~50 reclamações variadas
├── services/
│   ├── gateway/                     # FastAPI: valida JWT e faz proxy
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/{main.py, auth.py, proxy.py, settings.py}
│   ├── auth_service/                # FastAPI: /login, /me, seed do admin
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/{main.py, models.py, schemas.py, jwt_utils.py, routes.py, seed.py, db.py}
│   ├── complaint_service/           # FastAPI: CRUD reclamações + dispara orquestração
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/{main.py, models.py, schemas.py, routes.py, db.py, client_orchestrator.py}
│   ├── agent_orchestrator/          # FastAPI + LangGraph: guardrail → triagem → risco → relatório → guardrail saída
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/{main.py, graph.py, routes.py, llm.py,
│   │             agents/{triage.py, risk.py, report.py},
│   │             guardrails/{input_guard.py, output_guard.py},
│   │             rag/policy_loader.py}
│   └── report_service/              # FastAPI: dashboard JSON + relatório HTML + ADR HTML
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/{main.py, routes.py, dashboard.py, html_report.py, adr_builder.py, db.py,
│                 templates/{report.html.j2, adr.html.j2}}
└── frontend/
    ├── Dockerfile                    # build → nginx servindo estáticos
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.tsx, App.tsx, routes.tsx
        ├── api/client.ts             # axios + interceptor JWT
        ├── auth/{AuthContext.tsx, ProtectedRoute.tsx, useAuth.ts}
        ├── pages/{Login.tsx, Dashboard.tsx, Complaints.tsx, ComplaintDetail.tsx, NewComplaint.tsx, Reports.tsx}
        └── components/{Layout.tsx, CategoryChart.tsx, UrgencyBadge.tsx, CriticalList.tsx}
```

---

## Fluxos chave

### 1. Login com JWT
1. `frontend/Login.tsx` → POST `/api/auth/login` (gateway).
2. Gateway encaminha para `auth_service` que valida bcrypt e devolve JWT (HS256, exp 24h, claim `sub`=user_id).
3. Frontend guarda em `localStorage`; `client.ts` injeta `Authorization: Bearer ...` em todas as requisições.
4. Gateway valida o JWT em todo request não-`/login`, decodifica e propaga `X-User-Id` aos serviços internos.
5. **Admin inicial**: na primeira subida, `auth_service/seed.py` lê `ADMIN_EMAIL`/`ADMIN_PASSWORD` do `.env` e cria o usuário se não existir. Idempotente.

### 2. Análise de uma reclamação (Nível 3 completo)
1. `POST /api/complaints` (com texto) → `complaint_service` persiste a reclamação como `status=Aberta`.
2. `complaint_service` chama `POST agent_orchestrator/analyze` síncrono (texto + id).
3. `agent_orchestrator` executa o grafo LangGraph:
   - **Nó `input_guard`** (Bedrock Guardrail): se BLOCK → retorna mensagem educada em português; se PASS → segue.
   - **Nó `triage`** (Claude Haiku): categoria, produto, sentimento, urgência, resumo. Ofuscação de palavras impróprias no resumo.
   - **Nó `risk`** (Claude Sonnet): nível de risco (Baixo/Médio/Alto/Crítico) + justificativa, com RAG do `politica_interna.md`.
   - **Nó `report_generator`** (Haiku): consolida em payload estruturado.
   - **Nó `output_guard`**: verifica ausência de PII (regex CPF, conta) e tom profissional. Se falhar, sanitiza ou redacta.
4. `complaint_service` persiste o resultado em `complaints.analysis` e atualiza status.
5. Frontend exibe na `ComplaintDetail`.

### 3. Relatório gerencial e ADR
- `GET /api/reports/dashboard` → JSON com totais por categoria/produto/urgência, lista de críticas, recomendações.
- `GET /api/reports/html` → relatório HTML renderizado por Jinja2 com gráficos (Chart.js inline) — atende o requisito do dataset .html.
- `GET /api/reports/adr` → ADR HTML navegável (contexto, alternativas, decisão, custos por modelo, recomendações de segurança). Renderizado a partir de template Jinja com dados reais de uso.

### 4. Verificação de segurança (`make security-scan`)
Script `infra/security/scan.sh` roda em sequência:
- **Bandit** em cada `services/*/app/`
- **Semgrep** com regras `p/python`, `p/owasp-top-ten`, `p/jwt`
- **pip-audit** em cada `requirements.txt`
- **npm audit --omit=dev** no `frontend/`
- **Trivy** em cada imagem Docker construída
- Saída consolidada em `infra/security/report-YYYYMMDD.md` (resumo de findings por severidade).
Roda dentro de containers efêmeros (`aquasec/trivy`, `returntocorp/semgrep`) para não exigir instalação local.

---

## Modelo de dados (PostgreSQL — único banco, schemas separados)

- **schema `auth`**: `users(id uuid pk, email unique, password_hash, role, created_at)`
- **schema `complaints`**: `complaints(id uuid pk, external_id text, raw_text, channel, product_hint, status, created_at, created_by_user_id)` + `analyses(id uuid pk, complaint_id fk, category, product, sentiment, urgency, summary, risk_level, risk_justification, raw_payload jsonb, created_at)`
- **schema `reports`**: `report_runs(id uuid pk, generated_at, totals jsonb, file_path)` — registra cada geração de HTML.

`infra/postgres/init.sql` cria os schemas no startup; cada serviço usa SQLAlchemy + Alembic com `version_table_schema` próprio.

---

## Variáveis no `.env.example`
```
# Admin inicial (seed do auth_service)
ADMIN_EMAIL=admin@finguard.local
ADMIN_PASSWORD=Troque@123

# JWT
JWT_SECRET=change-me-32-bytes-min
JWT_ALG=HS256
JWT_EXP_HOURS=24

# Postgres
POSTGRES_USER=finguard
POSTGRES_PASSWORD=finguard
POSTGRES_DB=finguard

# AWS Bedrock
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
BEDROCK_MODEL_TRIAGE=anthropic.claude-3-haiku-20240307-v1:0
BEDROCK_MODEL_RISK=anthropic.claude-sonnet-4-6-v1:0
BEDROCK_GUARDRAIL_ID=
BEDROCK_GUARDRAIL_VERSION=DRAFT

# URLs internas (rede compose)
AUTH_SERVICE_URL=http://auth_service:8001
COMPLAINT_SERVICE_URL=http://complaint_service:8002
ORCHESTRATOR_URL=http://agent_orchestrator:8003
REPORT_SERVICE_URL=http://report_service:8004
```

---

## Stack técnica resumida

| Camada | Tecnologia |
|---|---|
| Backend microsserviços | FastAPI 0.115+, Pydantic v2, SQLAlchemy 2, Alembic, httpx |
| Auth | bcrypt (passlib), python-jose para JWT |
| Orquestração agêntica | LangGraph, langchain-aws, boto3 |
| Guardrails | Bedrock Guardrails (boto3 `apply_guardrail`) |
| RAG | Indexação simples em memória (FAISS-cpu opcional) sobre `politica_interna.md` |
| Banco | PostgreSQL 16 |
| Frontend | React 18, Vite, TypeScript, axios, react-router-dom, Chart.js (react-chartjs-2) |
| Container | Docker + docker compose v2; nginx servindo o build do front |
| Segurança | Bandit, Semgrep, pip-audit, npm audit, Trivy |

---

## Verificação end-to-end

Após implementar, para considerar pronto:

1. **Subir stack**: `docker compose up -d --build` deve levantar 7 containers (gateway, 4 services, postgres, frontend) sem erro. `docker compose ps` mostra todos `healthy`.
2. **Seed do admin**: logs do `auth_service` mostram "admin user created" na primeira execução; nas seguintes, "admin already exists".
3. **Login**: abrir `http://localhost:3000`, logar com `ADMIN_EMAIL`/`ADMIN_PASSWORD`, ser redirecionado ao dashboard.
4. **Dataset sintético**: `make generate-data` cria `data/synthetic_complaints.csv` com ~50 reclamações; `make seed-complaints` envia ao backend.
5. **Análise feliz**: enviar uma reclamação ("Fui cobrado duas vezes na fatura...") e verificar que volta JSON com categoria, produto, sentimento, urgência, resumo, risco — todos coerentes.
6. **Guardrail de entrada**: enviar prompt injection ("Ignore previous instructions...") e verificar bloqueio educado em PT-BR sem expor internals.
7. **Guardrail de saída**: enviar reclamação contendo CPF e verificar que o resumo retornado tem o CPF redactado/removido.
8. **Relatório HTML**: `GET /api/reports/html` baixa um arquivo HTML com gráfico funcional.
9. **ADR**: `GET /api/reports/adr` abre ADR navegável com seções: contexto, alternativas, decisão, custos, segurança.
10. **Security scan**: `make security-scan` produz `infra/security/report-*.md` com 0 findings críticos (ou justificativa para os existentes).

---

## Avisos de complexidade (Karpathy: simplicidade primeiro)

A combinação **microsserviços reais + Nível 3 + Bedrock + scan de segurança** é ambiciosa para uma janela curta. Riscos a observar durante a execução:
- **Bedrock acesso**: o Guardrail precisa ser criado previamente no console AWS (`BEDROCK_GUARDRAIL_ID`). Sem isso, o nó de input_guard falha. Documento o passo no README.
- **Latência síncrona**: `complaint_service` chama `agent_orchestrator` síncrono — uma reclamação pode levar 5-15s. Aceitável para demo; se virar gargalo, evoluir depois para fila.
- **Auth service-to-service**: por simplicidade, o gateway é a única fronteira de auth; serviços internos confiam na rede do compose (não expostos na máquina). Documentado nas recomendações de segurança do ADR.
- **Sem refresh token na v1**: expiração de 24h, re-login na expiração. Suficiente para o desafio.

Se em qualquer momento isso ficar inviável no tempo disponível, o caminho de degradação é: trocar microsserviços por modular monolito mantendo o resto.

---

## Ordem de execução sugerida

1. Estrutura de diretórios + `docker-compose.yml` + `.env.example` + `Makefile`.
2. `auth_service` + Postgres + seed do admin → testar login pelo gateway via curl.
3. Frontend mínimo: tela de login + AuthContext + Dashboard vazio.
4. `complaint_service` (CRUD básico, sem orquestração ainda) + tela de listar/criar reclamação.
5. `agent_orchestrator` v1 sem guardrails: triage → risk → report (LangGraph) com Bedrock.
6. Adicionar nós de `input_guard` e `output_guard` no grafo.
7. `report_service`: dashboard JSON, HTML report (Jinja+Chart.js), ADR HTML.
8. `scripts/generate_synthetic.py` + endpoint de bulk seed.
9. `infra/security/scan.sh` + `make security-scan` + corrigir findings.
10. README final com instruções de subida, criação do Guardrail no Bedrock, e como rodar o scan.
