# FinGuard — Log de execução do projeto

Registro cronológico da construção do projeto, na ordem em que cada arquivo foi criado, com a responsabilidade de cada um.

> Total: **89 arquivos** distribuídos em 7 áreas (esqueleto, auth_service, gateway, complaint_service, agent_orchestrator, report_service, frontend, scripts e infra/security).

---

## Fase 0 — Planejamento

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 0.1 | `PLAN.md` | Plano completo aprovado: contexto, arquitetura, estrutura de diretórios, fluxos chave (login, análise, relatório), modelo de dados, variáveis de ambiente, stack, verificação end-to-end, avisos de complexidade e ordem de execução. |

---

## Fase 1 — Esqueleto da estrutura

Objetivo: criar a base que orquestra todos os containers, define variáveis e atalhos operacionais.

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 1.1 | `.env.example` | Modelo das variáveis de ambiente: admin inicial, JWT, Postgres, AWS Bedrock (modelos + Guardrail ID), URLs internas dos serviços, base URL do frontend. |
| 1.2 | `.gitignore` | Exclui `.env`, caches Python/Node, `dist/`, volumes do Postgres, relatórios de scan e CSVs gerados. |
| 1.3 | `docker-compose.yml` | Define os 7 containers (`postgres`, `auth_service`, `complaint_service`, `agent_orchestrator`, `report_service`, `gateway`, `frontend`), rede `finguard_net`, volume `postgres-data` e mounts `data/`/`docs/` para o report_service. Apenas `gateway:8000` e `frontend:3000` expostos no host. |
| 1.4 | `Makefile` | Atalhos: `up`, `down`, `build`, `logs`, `ps`, `restart`, `clean`, `generate-data`, `seed-complaints`, `security-scan`. |
| 1.5 | `infra/postgres/init.sql` | Roda no startup do container Postgres — cria schemas `auth`, `complaints`, `reports` e habilita `pgcrypto`. Garante isolamento por serviço dentro do mesmo banco. |

---

## Fase 2 — `auth_service` (autenticação + seed do admin)

Objetivo: serviço autônomo de autenticação que gera o JWT consumido pelo gateway.

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 2.1 | `services/auth_service/requirements.txt` | FastAPI, Uvicorn, SQLAlchemy 2, psycopg, passlib[bcrypt], python-jose, pydantic-settings. |
| 2.2 | `services/auth_service/Dockerfile` | Imagem `python:3.12-slim`, instala deps, expõe 8001, roda `uvicorn`. |
| 2.3 | `services/auth_service/app/__init__.py` | Marca o pacote Python. |
| 2.4 | `services/auth_service/app/settings.py` | Carrega variáveis via Pydantic Settings; expõe `database_url` montada a partir das vars de Postgres. |
| 2.5 | `services/auth_service/app/db.py` | Engine SQLAlchemy + `SessionLocal` + `Base` declarativo + dependência `get_db()` para o FastAPI. |
| 2.6 | `services/auth_service/app/models.py` | Modelo `User` no schema `auth` (id UUID, email único, name, password_hash, role, created_at). |
| 2.7 | `services/auth_service/app/schemas.py` | Pydantic: `LoginRequest`, `TokenResponse`, `UserOut`. |
| 2.8 | `services/auth_service/app/jwt_utils.py` | `hash_password`/`verify_password` (bcrypt) e `create_access_token` (HS256, exp configurável). |
| 2.9 | `services/auth_service/app/seed.py` | `seed_admin()` idempotente: cria o usuário admin a partir de `ADMIN_EMAIL`/`ADMIN_PASSWORD` se ainda não existir. |
| 2.10 | `services/auth_service/app/routes.py` | Endpoints: `POST /login` (valida credenciais e devolve JWT), `GET /me` (retorna dados do user pelo header `X-User-Id` propagado pelo gateway), `GET /healthz`. |
| 2.11 | `services/auth_service/app/main.py` | App FastAPI; `on_startup` aguarda Postgres ficar pronto (retry), executa `Base.metadata.create_all` e roda `seed_admin()`. |

---

## Fase 3 — `gateway` (única porta exposta)

Objetivo: validar JWT, propagar identidade aos serviços internos e fazer proxy.

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 3.1 | `services/gateway/requirements.txt` | FastAPI, Uvicorn, python-jose, httpx. |
| 3.2 | `services/gateway/Dockerfile` | Imagem slim, expõe 8000. |
| 3.3 | `services/gateway/app/__init__.py` | Marca o pacote. |
| 3.4 | `services/gateway/app/settings.py` | JWT secret/alg + URLs internas dos 4 serviços. |
| 3.5 | `services/gateway/app/auth.py` | `decode_jwt()` e dependência `require_user` que extrai o `Authorization: Bearer …` e devolve as claims. |
| 3.6 | `services/gateway/app/proxy.py` | `forward()`: encaminha método/headers/query/body ao serviço interno, removendo headers hop-by-hop e o `Authorization` original; injeta `X-User-Id`/`X-User-Email`/`X-User-Role` a partir das claims. |
| 3.7 | `services/gateway/app/main.py` | Rotas: `/api/auth/login` pública; tudo mais sob `/api/{auth,complaints,reports,orchestrator}/*` protegido por `require_user`. CORS aberto para o frontend local. |

---

## Fase 4 — `complaint_service` (CRUD + ponte para o orquestrador)

Objetivo: persistir reclamações e disparar a análise no `agent_orchestrator`.

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 4.1 | `services/complaint_service/requirements.txt` | FastAPI, SQLAlchemy 2, psycopg, httpx. |
| 4.2 | `services/complaint_service/Dockerfile` | Imagem slim, expõe 8002. |
| 4.3 | `services/complaint_service/app/__init__.py` | Marca o pacote. |
| 4.4 | `services/complaint_service/app/settings.py` | Vars de Postgres + `ORCHESTRATOR_URL`. |
| 4.5 | `services/complaint_service/app/db.py` | Engine + Session + Base — dono dos seus próprios objetos (independência de microsserviço). |
| 4.6 | `services/complaint_service/app/models.py` | `Complaint` (raw_text, channel, product_hint, status, created_by_user_id) e `Analysis` (blocked, category, product, sentiment, urgency, summary, risk_level, raw_payload JSONB). Schema `complaints`. |
| 4.7 | `services/complaint_service/app/schemas.py` | DTOs Pydantic: `ComplaintCreate`, `ComplaintBulkCreate`, `AnalysisOut`, `ComplaintOut`, `BulkResult`. |
| 4.8 | `services/complaint_service/app/client_orchestrator.py` | `analyze_complaint()`: chamada HTTP síncrona ao `agent_orchestrator/analyze` com tratamento de falha. |
| 4.9 | `services/complaint_service/app/routes.py` | Endpoints `POST /` (cria + analisa), `POST /bulk` (lote para o seed), `GET /` (lista paginada), `GET /{id}` (detalhe), `GET /healthz`. Persiste resultado da análise e atualiza status (`Resolvida`/`Bloqueada`/`Falha`). |
| 4.10 | `services/complaint_service/app/main.py` | App FastAPI; `on_startup` aguarda Postgres e cria tabelas. |

---

## Fase 5 — `agent_orchestrator` (LangGraph + Bedrock + Guardrails)

Objetivo: executar o grafo de 5 nós que faz triagem, análise de risco e bloqueio/sanitização.

### 5a. Política interna (RAG)

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 5.1 | `data/politica_interna.md` | Documento fictício consumido pelo agente de risco como contexto: critérios de risco, regras de escalação, conformidade (LGPD, sigilo bancário), peso de canais (Banco Central, Procon, redes sociais). |

### 5b. Estrutura do serviço

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 5.2 | `services/agent_orchestrator/requirements.txt` | FastAPI, boto3, langgraph, langchain-core, langchain-aws. |
| 5.3 | `services/agent_orchestrator/Dockerfile` | Imagem slim, expõe 8003. |
| 5.4 | `services/agent_orchestrator/app/__init__.py` | Pacote. |
| 5.5 | `services/agent_orchestrator/app/settings.py` | Credenciais AWS, IDs de modelo (triage/risk/report), Guardrail ID/version, caminho da política. |
| 5.6 | `services/agent_orchestrator/app/llm.py` | Cliente Bedrock; `invoke_claude()` (Messages API), `parse_json_object()` (tolerante a markdown fences), `apply_guardrail()` (no-op se não configurado). |

### 5c. RAG

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 5.7 | `services/agent_orchestrator/app/rag/__init__.py` | Pacote. |
| 5.8 | `services/agent_orchestrator/app/rag/policy_loader.py` | Carrega `politica_interna.md` em memória (cache); usado pelo agente de risco como contexto. |

### 5d. Agentes do grafo

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 5.9 | `services/agent_orchestrator/app/agents/__init__.py` | Pacote. |
| 5.10 | `services/agent_orchestrator/app/agents/triage.py` | Nó de triagem (Claude Haiku): classifica categoria, produto, sentimento, urgência e gera resumo. Mascaramento de palavras impróprias por regex. |
| 5.11 | `services/agent_orchestrator/app/agents/risk.py` | Nó de risco (Claude Sonnet) com RAG da política interna: define `risk_level` + `risk_justification`. |
| 5.12 | `services/agent_orchestrator/app/agents/report.py` | Consolida triagem + risco em payload final estruturado (puro Python — sem LLM extra para economizar). |

### 5e. Guardrails

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 5.13 | `services/agent_orchestrator/app/guardrails/__init__.py` | Pacote. |
| 5.14 | `services/agent_orchestrator/app/guardrails/input_guard.py` | Aplica Bedrock Guardrail no texto de entrada; retorna `allowed` + mensagem educada de bloqueio em PT-BR. |
| 5.15 | `services/agent_orchestrator/app/guardrails/output_guard.py` | Sanitiza PII (CPF, conta, cartão) por regex em `summary` e `risk_justification` antes da resposta sair. |

### 5f. Grafo e API

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 5.16 | `services/agent_orchestrator/app/graph.py` | Define `AnalysisState` (TypedDict) e monta o grafo LangGraph: `input_guard` → (BLOCK → END | PASS → `triage` → `risk` → `report` → `output_guard` → END). Logs estruturados de tempo por nó. |
| 5.17 | `services/agent_orchestrator/app/routes.py` | `POST /analyze`: invoca o grafo e devolve payload. Se bloqueado, retorna `blocked=true` + `block_reason` + campos null. |
| 5.18 | `services/agent_orchestrator/app/main.py` | App FastAPI mínima, `on_startup` apenas loga prontidão. |

---

## Fase 6 — `report_service` (dashboard + HTML report + ADR)

Objetivo: agregar dados das reclamações para visualização gerencial e gerar o ADR navegável.

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 6.1 | `services/report_service/requirements.txt` | FastAPI, SQLAlchemy 2, psycopg, Jinja2. |
| 6.2 | `services/report_service/Dockerfile` | Imagem slim, expõe 8004. |
| 6.3 | `services/report_service/app/__init__.py` | Pacote. |
| 6.4 | `services/report_service/app/settings.py` | Vars Postgres + diretórios de saída (`/app/reports`, `/app/docs`) + IDs dos modelos para exibir no ADR. |
| 6.5 | `services/report_service/app/db.py` | Engine + Session (somente leitura na prática). |
| 6.6 | `services/report_service/app/dashboard.py` | `build_dashboard()`: query consolidada via SQL, agrupamentos por categoria/produto/urgência/risco/sentimento, lista de críticas, geração de recomendações textuais. |
| 6.7 | `services/report_service/app/html_report.py` | Renderiza `report.html.j2` (gráficos por categoria/produto/urgência/risco com Chart.js inline) e opcionalmente salva em `data/reports/`. |
| 6.8 | `services/report_service/app/adr_builder.py` | Renderiza `adr.html.j2` com modelos Bedrock atuais e estatísticas de uso; salva em `docs/adr.html`. |
| 6.9 | `services/report_service/app/routes.py` | Endpoints `GET /dashboard` (JSON), `GET /html` (relatório), `GET /adr`, `GET /healthz`. Suporta `?save=true` para escrever em volume. |
| 6.10 | `services/report_service/app/main.py` | App FastAPI, aguarda Postgres no startup. |
| 6.11 | `services/report_service/app/templates/report.html.j2` | Template do relatório gerencial com KPIs, 4 gráficos Chart.js, tabela de críticas e recomendações. |
| 6.12 | `services/report_service/app/templates/adr.html.j2` | Template ADR navegável: contexto, alternativas, decisão, consequências, custos por modelo, recomendações de segurança. |

---

## Fase 7 — Frontend React + Vite + TypeScript

Objetivo: SPA com login JWT, dashboards, CRUD de reclamações e portal para os relatórios.

### 7a. Configuração

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 7.1 | `frontend/package.json` | Dependências: React 18, axios, react-router-dom 6, chart.js, react-chartjs-2; dev: Vite, TS. |
| 7.2 | `frontend/tsconfig.json` | TypeScript estrito, JSX `react-jsx`, módulo ESNext. |
| 7.3 | `frontend/vite.config.ts` | Plugin React + dev server. |
| 7.4 | `frontend/index.html` | Mount point `#root`, importa `/src/main.tsx`. |
| 7.5 | `frontend/nginx.conf` | SPA fallback (`try_files $uri /index.html`) + gzip. |
| 7.6 | `frontend/Dockerfile` | Multi-stage: build Node 20 → estático servido por nginx 1.27. Recebe `VITE_API_BASE_URL` por build arg. |

### 7b. Bootstrap

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 7.7 | `frontend/src/main.tsx` | Bootstrap React: BrowserRouter + AuthProvider envolvendo `<App/>`. |
| 7.8 | `frontend/src/index.css` | Reset + design tokens (cards, pills, botões, tabelas, formulários). |
| 7.9 | `frontend/src/App.tsx` | Roteamento: `/login` público; sob `ProtectedRoute + Layout`: `/`, `/complaints`, `/complaints/new`, `/complaints/:id`, `/reports`. |

### 7c. API client

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 7.10 | `frontend/src/api/client.ts` | Instância axios com `VITE_API_BASE_URL`; interceptor de request injeta `Authorization: Bearer …`; interceptor de response força redirecionamento ao `/login` em 401. Exporta tipos `Complaint`, `Analysis`, `DashboardData`. |

### 7d. Autenticação

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 7.11 | `frontend/src/auth/AuthContext.tsx` | Provider que persiste o JWT no `localStorage`, decodifica claims, expõe `login()`/`logout()`. |
| 7.12 | `frontend/src/auth/useAuth.ts` | Hook fino para consumir o contexto. |
| 7.13 | `frontend/src/auth/ProtectedRoute.tsx` | Wrapper de rotas: redireciona para `/login` se sem usuário. |

### 7e. Componentes compartilhados

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 7.14 | `frontend/src/components/Layout.tsx` | Header + nav (Dashboard / Reclamações / Nova / Relatórios) + e-mail + botão sair; `<Outlet/>` para as páginas. |
| 7.15 | `frontend/src/components/UrgencyBadge.tsx` | Pill colorido por nível (crit/alta/media/baixa). Usado em listas e detalhe. |
| 7.16 | `frontend/src/components/CategoryChart.tsx` | Wrapper Chart.js (Bar) configurado para categorias do dashboard. |

### 7f. Páginas

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 7.17 | `frontend/src/pages/Login.tsx` | Form de e-mail/senha → `useAuth().login()` → redireciona para `/`. |
| 7.18 | `frontend/src/pages/Dashboard.tsx` | Consome `/api/reports/dashboard`, mostra 3 KPIs e 4 gráficos + recomendações. |
| 7.19 | `frontend/src/pages/Complaints.tsx` | Lista paginada das reclamações com triagem e risco resumidos. |
| 7.20 | `frontend/src/pages/NewComplaint.tsx` | Form (canal, produto opcional, texto) → `POST /api/complaints/` → redireciona para detalhe. |
| 7.21 | `frontend/src/pages/ComplaintDetail.tsx` | Mostra texto original + bloco de bloqueio (se guardrail interveio) ou painéis de Triagem e Risco lado a lado. |
| 7.22 | `frontend/src/pages/Reports.tsx` | Botões para abrir/salvar o relatório HTML e o ADR; aviso sobre token JWT no header. |

---

## Fase 8 — Scripts auxiliares

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 8.1 | `scripts/generate_synthetic.py` | Gera `data/synthetic_complaints.csv` com ~50 reclamações fictícias variadas (cobrança indevida, fraude com CPF/cartão, ameaça regulatória, prompt injection, palavrões, neutras/positivas). |
| 8.2 | `scripts/seed_complaints.py` | Lê o CSV, faz login via `/api/auth/login`, envia tudo em `POST /api/complaints/bulk` (cada item dispara o pipeline completo). |

---

## Fase 9 — Verificação de segurança

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 9.1 | `infra/security/scan.sh` | Roda Bandit, Semgrep (p/python + owasp-top-ten + jwt), pip-audit (por serviço), npm audit (frontend) e Trivy (imagens) — tudo em containers efêmeros. Salva saídas brutas em `infra/security/raw/` e relatório consolidado em `infra/security/report-YYYYMMDD-HHMMSS.md`. |
| 9.2 | `infra/security/README.md` | Documenta o que cada scanner cobre, pré-requisitos (apenas Docker), políticas de tratamento de findings. |

---

## Fase 10 — Documentação final

| # | Arquivo | Responsabilidade |
|---|---------|------------------|
| 10.1 | `README.md` | Documento de entrada do projeto: visão da arquitetura, pré-requisitos, configuração do `.env`, como criar o Bedrock Guardrail, comandos `make`, fluxo de uso, cenários para a banca, justificativa de custos, estrutura de diretórios, limitações conhecidas e avisos do desafio (dataset sintético, sem cloud). |
| 10.2 | `execution.md` | **Este arquivo.** Log cronológico da montagem com responsabilidade de cada arquivo. |

---

## Resumo por porta exposta

| Porta | Container          | Para quê serve no host |
|-------|--------------------|------------------------|
| 3000  | `frontend`         | UI React (nginx)       |
| 8000  | `gateway`          | Único endpoint público da API |
| —     | `auth_service`     | Apenas rede interna (8001 dentro do compose) |
| —     | `complaint_service`| Apenas rede interna (8002) |
| —     | `agent_orchestrator`| Apenas rede interna (8003) |
| —     | `report_service`   | Apenas rede interna (8004) |
| —     | `postgres`         | Apenas rede interna (5432) |

---

## Pontos de extensão futuros

- Trocar chamadas síncronas a `agent_orchestrator` por fila (SQS / RabbitMQ) com atualização via SSE.
- JWT RS256 com rotação de chaves e refresh token em cookie HttpOnly.
- mTLS ou JWTs internos entre serviços (hoje confiamos na rede do Compose).
- Métricas reais de tokens/custo do CloudWatch alimentando o ADR.
- Cluster do Postgres por serviço (purismo de microsserviços) caso saia do desafio para produção real.
