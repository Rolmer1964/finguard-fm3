# FinGuard — Nível 3 (Arquiteto da Solução)


> Branch `feature/level-3` · Atende o Nível 3 do desafio Future Minds 3.
> Versão anterior em `feature/level-2`.

Sistema **multi-agente orquestrado com guardrails, RAG e ADR**, que recebe uma reclamação de cliente, valida a entrada via Bedrock Guardrails, classifica, avalia risco com base na Política Interna e gera relatório gerencial agregado — com proteção de dados sensíveis na saída.

## Pipeline

```
reclamação ──► [✓ Guardrail Entrada] ──PASS──► [① Triagem]  Claude Haiku
                     │                                 │
                  BLOCKED                              ▼
                     │                         [② Risco + RAG]  Claude Sonnet
                     ▼                                 │         + Titan Embed + FAISS
              [resposta educada]                       ▼
                     │                         [③ Relatório]  consolidação determinística
                     │                                 │
                     │                                 ▼
                     └──────────────────► [✓ Guardrail Saída]  sanitiza PII
                                                        │
                                                        ▼
                                                   JSON final
```

Construído com **LangGraph** + **Bedrock** (boto3). Cada nó loga **entrada, saída e tempo** com um `trace_id` para rastreabilidade.

---

## Pré-requisitos

- Docker Desktop em execução.
- Conta AWS com acesso a Bedrock e modelos Claude habilitados.
- (Opcional, recomendado) Bedrock Guardrail provisionado via `scripts/create_guardrail.py`.

## Setup

```bash
cp .env.example .env
# editar AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# opcionalmente: GUARDRAIL_ID=<id gerado pelo create_guardrail.py>
make up
```

- UI: http://localhost:8000
- API: http://localhost:8000/analyze
- ADR: http://localhost:8000/adr

## Provisionamento do Guardrail (Nível 3)

```bash
# Cria o guardrail no Bedrock (execute uma vez):
python scripts/create_guardrail.py --region us-east-1
# Copie GUARDRAIL_ID=<id> para .env e reinicie o container
```

Sem o guardrail configurado, o sistema usa um fallback local baseado em heurísticas (cobre injeção básica, mas é menos robusto).

## Uso

### Pela UI
Acesse http://localhost:8000, cole a reclamação e clique em **Executar pipeline**. O pipeline mostra guardrail de entrada, triagem, risco, relatório e guardrail de saída — com timings de cada etapa.

### Pela API (uma reclamação)
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"Já é a terceira vez que ligo pedindo o estorno de uma cobrança no meu cartão que eu não fiz. Vou procurar o Banco Central."}'
```

Resposta (caso aprovado pelo guardrail):
```json
{
  "trace_id": "a3f1c0d8",
  "blocked": false,
  "category": "Cobrança Indevida",
  "product": "Cartão de Crédito",
  "sentiment": "Crítico",
  "urgency": "Alta",
  "summary": "Cliente relata cobrança não reconhecida no cartão de crédito...",
  "risk_level": "Alto",
  "risk_justification": "Menção a órgão regulador eleva o risco...",
  "timings_ms": {"guardrail_input": 12, "triage": 1240, "risk": 2880, "report": 0, "guardrail_output": 8}
}
```

Resposta (caso bloqueado pelo guardrail):
```json
{
  "trace_id": "b7e2a1f0",
  "blocked": true,
  "message": "Esta entrada não pode ser processada pelo FinGuard..."
}
```

### Em lote (CSV → JSON + CSV + MD + HTML)

| Dataset | Tamanho | Como usar |
|---|---|---|
| `data/synthetic_complaints.csv` | ~50 (dev) | `make generate-data && make batch` |
| `scripts/reclamacoes_bancarias_500.csv` | 500 (oficial) | `make batch-500` |

Saídas em `./output/`:
- `<nome>.json` — payload completo
- `<nome>.csv` — para Excel/Sheets
- `<nome>.md` — relatório gerencial em Markdown
- `<nome>.html` — relatório com gráficos (Chart.js)

> ⚠️ 500 reclamações × 2 chamadas LLM + 1 embedding = leva minutos e tem custo. Para dev, use o dataset menor.

---

## RAG semântico (Bedrock Embeddings + FAISS)

O agente de risco recebe apenas os **top-K trechos** mais relevantes da Política Interna, recuperados de um índice FAISS local.

```bash
make rag-ingest    # incremental: só novos/alterados re-embeddaram
make rag-status    # mostra arquivos indexados, chunks, hash
```

---

## Guardrails (Nível 3)

| Guardrail | Mecanismo | O que bloqueia/sanitiza |
|---|---|---|
| Entrada | Bedrock Guardrails + fallback local | Prompt injection, conteúdo inválido, ameaças |
| Saída | Bedrock Guardrails + regex | CPF, número de conta, cartão de crédito, e-mail, telefone |

---

## ADR (Architectural Decision Record)

Disponível em http://localhost:8000/adr ou no arquivo `assets/adr.html`.

Documenta: contexto, 3 opções de arquitetura consideradas, decisão final, análise de custos por modelo, trade-offs e recomendações de segurança.

---

## Logs rastreáveis

`make logs` mostra a execução de cada agente:
```
[a3f1c0d8] GRAPH START
[a3f1c0d8] AGENT=guardrail_input IN text_len=287
[a3f1c0d8] AGENT=guardrail_input OUT in 12ms blocked=False reason=None
[a3f1c0d8] AGENT=triage IN text_len=287 product_hint=None
[a3f1c0d8] AGENT=triage OUT in 1240ms category=Cobrança Indevida urgency=Alta
[a3f1c0d8] AGENT=risk IN triage_keys=[...]
[a3f1c0d8] AGENT=risk OUT in 2880ms level=Alto rag_chunks=4
[a3f1c0d8] AGENT=report OUT in 0ms
[a3f1c0d8] AGENT=guardrail_output OUT in 8ms
[a3f1c0d8] GRAPH END timings={...}
```

---

## Estrutura

```
├── docker-compose.yml
├── .env.example
├── Makefile
├── assets/
│   ├── adr.html               # ADR navegável (Nível 3)
│   ├── docs/                  # entrada do RAG (PDFs/MDs)
│   └── index/                 # FAISS + manifest (gitignored)
├── output/                    # relatórios gerados
├── scripts/
│   ├── create_guardrail.py    # provisiona Bedrock Guardrail (Nível 3)
│   ├── generate_synthetic.py
│   └── reclamacoes_bancarias_500.csv
└── app/src/
    ├── main.py                # FastAPI: rotas + admin + traces
    ├── graph.py               # LangGraph: guardrail→triage→risk→report→guardrail
    ├── settings.py            # AWS + modelos + guardrail + paths
    ├── agents/
    │   ├── guardrail.py       # Bedrock Guardrails + fallback (Nível 3)
    │   ├── triage.py          # Haiku
    │   ├── risk.py            # Sonnet + RAG
    │   └── report.py          # consolidação
    ├── rag/                   # FAISS + Titan Embeddings
    └── templates/             # index, result, report (Jinja2)
```

## Avisos

- Dataset **exclusivamente sintético**, conforme as notas de compromisso do desafio.
- Tudo roda **localmente**; nada persistido em nuvem (sem S3).
- Desprovisionamento pós-hackathon: `python scripts/create_guardrail.py --delete <ID>`.
