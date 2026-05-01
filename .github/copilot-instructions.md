# FinGuard — Copilot Instructions

## Sobre o projeto

Sistema de análise de reclamações bancárias — Hackathon Future Minds 3, Nível 3, Grupo 23TB.
Pipeline multi-agente com AWS Bedrock, LangGraph e RAG sobre política interna (POL-SAC-001).

## Stack

- **Runtime**: Python 3.12, FastAPI, Docker Compose
- **IA**: AWS Bedrock — Claude Haiku 4.5 (triagem) + Claude Sonnet 4.5 (risco + RAG)
- **Guardrails**: AWS Bedrock Guardrails (IDs configuráveis via `.env`)
- **RAG**: FAISS + Amazon Titan Embed Text v2 (1024 dim)
- **Templates**: Jinja2 + Chart.js
- **Configuração**: Pydantic Settings carregada de `.env`

## Estrutura

```
app/src/
  main.py              # FastAPI app, rotas, loop AIMD de batch
  graph.py             # Pipeline LangGraph, trace store (deque)
  report_writer.py     # write_outputs() — gera JSON/CSV/MD/HTML
  relatorio_tecnico.py # Serve assets/relatorio-tecnico.html como rota
  settings.py          # Pydantic Settings (lê do .env)
  models.py            # AnalyzeRequest (Pydantic)
  helpers.py           # Funções auxiliares de template (pill_html, bar_width_px…)
  llm.py               # Clientes Bedrock (Haiku, Sonnet)
  profanity.py         # mask() — filtro local de palavrões
  agents/
    guardrail.py       # check_input / sanitize_output (Bedrock + regex + profanity)
    triage.py          # Haiku — categoria, produto, sentimento, urgência
    risk.py            # Sonnet + RAG — nível de risco, justificativa, ações
    report.py          # consolidate() — overrides POL-SAC-001, SLA, área responsável
  guardrails/          # Módulo alternativo de guardrails (input_guard, output_guard)
  rag/
    ingest.py          # ingest_all() — processa docs e atualiza índice FAISS
    loader.py          # Carrega PDFs/MDs de assets/docs/
    chunker.py         # Divide documentos em chunks
    embedder.py        # Titan Embed Text v2 (1024 dim)
    store.py           # Persiste/carrega índice FAISS + manifest
    retriever.py       # Busca semântica — top-k chunks para o contexto do Sonnet
  templates/
    index.html.j2          # Formulário individual com seleção de canal
    report.html.j2         # Relatório gerencial de batch
    reports.html.j2        # Listagem de relatórios
    traces.html.j2         # Log de execuções + estatísticas
    result.html.j2         # Resultado de registro individual
    admin.html.j2          # Painel admin (rebuild RAG)
    politica_decisoria.html.j2  # Painel Decisório dinâmico (POL-SAC-001)
    relatorio_tecnico.html.j2   # Relatório Técnico de Entrega
    _header.html.j2        # Header de navegação compartilhado
    _modal.html.j2         # Modal de detalhe compartilhado

assets/
  docs/              # PDFs/MDs fonte do RAG
  index/             # Índice FAISS + manifest (GITIGNORED, regenerável)
  adr.html           # ADR-001 — decisões arquiteturais
  relatorio-tecnico.html  # Relatório Técnico de Entrega (estático)
  presentation/      # Material do hackathon

data/                # Datasets (GITIGNORED)
output/              # Relatórios de runtime (GITIGNORED)
scripts/             # Utilitários: create_guardrail.py, rag_ingest.py…
```

## Pipeline

```
guardrail_input → triage (Haiku) → risk (Sonnet + RAG) → report → guardrail_output
```

- Registros bloqueados: `category = "Bloqueado"`, excluídos das estatísticas
- `timings_ms`: `guardrail_input`, `triage`, `risk`, `report`, `guardrail_output`

## Conformidade POL-SAC-001 — overrides em `report.py`

| Override | Condição | Efeito |
|---|---|---|
| 1 | Canal ∈ {Banco Central, Procon, Justiça} | urgência → Crítica |
| 2 | risk_level = Crítico | urgência mínima → Alta |
| 3 | Canal ∈ {Banco Central, Procon, Justiça} | risk_level mínimo → Alto |

SLA por urgência: Crítica=4h · Alta=24h · Média=3 dias úteis · Baixa=5 dias úteis

## Guardrail de saída — fluxo de sanitização

1. Bedrock (`source=OUTPUT`) — PII e conteúdo; usa `outputs[0]["text"]` sempre
2. Regex local — CPF, conta, cartão, nome com marcador contextual
3. `mask_profanity()` — última defesa em `texto_original`

Metadata em `guardrail_output_meta[]`: `bedrock_intervened`, `bedrock_detail` (pii_types, content, profanity), `pii` (contagens regex). Flag `profanity_masked` no payload final.

## Convenções

- Timezone: UTC-3 (BRT) — usar `now_brt()` de `settings.py`
- Stems de relatório: `report_YYYY-MM-DD-HH-MM-SS`
- `output/` e `data/` são gitignored
- Commits nunca incluem `Co-Authored-By`
- Linguagem do código e comentários: Português Brasil

## Endpoints principais

| Método | Rota | Descrição |
|---|---|---|
| POST | `/analyze` | Processa um registro (JSON: `text`, `product_hint`, `canal`) |
| POST | `/analyze-form` | Formulário web — salva relatório e redireciona para `/report/{stem}` |
| POST | `/batch` | Processa CSV em batch com AIMD |
| GET | `/report/{stem}` | Relatório HTML de batch ou consulta unitária |
| GET | `/api/record/{id}` | Registro por ID (usado pelo modal) |
| GET | `/api/decisorio/stats` | Estatísticas ao vivo para o Painel Decisório |
| GET | `/traces` | Log de execuções |

## Batch AIMD

Throttling adaptativo inspirado no controle de congestionamento TCP.
Parâmetros via `.env`: `BATCH_MAX_WORKERS`, `BATCH_RATE_LIMIT_DELAY`, `BATCH_MAX_RETRIES`, `BATCH_MAX_PASSES`, `BATCH_RETRY_DELAY`.
ThrottlingException > 5% → `workers // 2`, `delay += 1.0s`. Throttle = 0 → `workers + 1`, `delay -= 0.5s`.
