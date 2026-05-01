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
  main.py            # FastAPI app, rotas, loop AIMD de batch
  graph.py           # Pipeline LangGraph, trace store (deque)
  report_writer.py   # write_outputs() — gera JSON/CSV/MD/HTML
  settings.py        # Pydantic Settings
  agents/
    guardrail.py     # check_input / sanitize_output (Bedrock + regex + profanity)
    triage.py        # Haiku — categoria, produto, sentimento, urgência
    risk.py          # Sonnet + RAG — nível de risco, justificativa, ações
    report.py        # consolidate() — overrides POL-SAC-001, SLA, área responsável
  templates/         # Jinja2 (.html.j2)

assets/docs/         # PDFs/MDs fonte do RAG
data/                # Datasets (GITIGNORED)
output/              # Relatórios de runtime (GITIGNORED)
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
