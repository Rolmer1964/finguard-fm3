# FinGuard — Nível 2 (Orquestrador de Análise)

> Branch `feature/level-2` · Atende exclusivamente o Nível 2 do desafio Future Minds 3.
> Versão simplificada em `feature/level-1` · Versão completa em `feature/level-3`.

Sistema **multi-agente orquestrado** que recebe uma reclamação de cliente e gera análise estruturada com nível de risco, justificativa e relatório gerencial agregado.

## Pipeline

```
                  ┌──────────────────┐
   reclamação ──► │  Agente TRIAGEM  │  Claude 3 Haiku
                  │ (categoria,      │  (rápido e barato)
                  │  produto,        │
                  │  sentimento,     │
                  │  urgência,       │
                  │  resumo)         │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  Agente RISCO    │  Claude 3.5 Sonnet
                  │ (Baixo/Médio/    │  (raciocínio fino +
                  │  Alto/Crítico)   │   RAG da política)
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ Agente RELATÓRIO │  consolidação determinística
                  │ (consolida payload)  (zero LLM aqui)
                  └────────┬─────────┘
                           │
                           ▼
                       JSON final
```

Construído com **LangGraph** + **Bedrock** (boto3). Cada nó loga **entrada, saída e tempo** com um `trace_id` para rastreabilidade.

> Sem JWT, sem banco de dados, sem microsserviços, sem guardrails. **Apenas o que o Nível 2 pede** — multi-agente + logs rastreáveis + relatório em arquivo.

---

## Pré-requisitos

- Docker Desktop em execução.
- Conta AWS com acesso a Bedrock e aos dois modelos Claude habilitados.

## Setup

```bash
cp .env.example .env
# editar AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
make up
```

- UI simples: http://localhost:8000
- API: http://localhost:8000/analyze
- Batch: http://localhost:8000/batch

## Uso

### Pela UI
Acesse http://localhost:8000, cole a reclamação e clique em **Executar pipeline**. Você verá triagem + risco + timings de cada agente.

### Pela API (uma reclamação)
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"Já é a terceira vez que ligo pedindo o estorno de uma cobrança no meu cartão que eu não fiz. Vou procurar o Banco Central."}'
```

Resposta:
```json
{
  "trace_id": "a3f1c0d8",
  "category": "Cobrança Indevida",
  "product": "Cartão de Crédito",
  "sentiment": "Crítico",
  "urgency": "Alta",
  "summary": "Cliente relata cobrança não reconhecida no cartão de crédito, com três tentativas de contato sem resolução. Ameaça escalar para Banco Central.",
  "risk_level": "Alto",
  "risk_justification": "Caso envolve cobrança contestada com ameaça de escalação ao Banco Central. Conforme política interna, menção a órgãos reguladores eleva o risco em pelo menos um nível.",
  "timings_ms": {"triage": 1240, "risk": 2880, "report": 0}
}
```

### Em lote (CSV → JSON + CSV + MD + HTML)

Dois datasets disponíveis:

| Dataset | Tamanho | Como gerar/usar |
|---|---|---|
| `data/synthetic_complaints.csv` | ~50 (rápido, dev) | `make generate-data && make batch` |
| `scripts/reclamacoes_bancarias_500.csv` | 500 (oficial) | `make batch-500` |

Saídas em `./output/`:
- `<nome>.json` — payload completo de cada reclamação
- `<nome>.csv` — para Excel/Sheets
- `<nome>.md` — relatório gerencial em Markdown
- `<nome>.html` — relatório gerencial com gráficos (Chart.js) — visualize em http://localhost:8000/output/<nome>.html

> ⚠️ 500 reclamações × 2 chamadas LLM (triage + risk) = leva alguns minutos e tem custo. Para dev, use o dataset menor.

---

## Logs rastreáveis (requisito do Nível 2)

`make logs` mostra a execução de cada agente. Exemplo:
```
[a3f1c0d8] GRAPH START
[a3f1c0d8] AGENT=triage IN text_len=287 product_hint=None
[a3f1c0d8] AGENT=triage OUT in 1240ms category=Cobrança Indevida product=Cartão de Crédito urgency=Alta
[a3f1c0d8] AGENT=risk IN triage_keys=['category', 'product', 'sentiment', 'urgency', 'summary']
[a3f1c0d8] AGENT=risk OUT in 2880ms level=Alto
[a3f1c0d8] AGENT=report IN
[a3f1c0d8] AGENT=report OUT in 0ms
[a3f1c0d8] GRAPH END timings={'triage': 1240, 'risk': 2880, 'report': 0}
```

---

## Estrutura

```
MARCELO/
├── docker-compose.yml         # 1 serviço
├── .env.example
├── Makefile
├── data/
│   ├── politica_interna.md    # base RAG do agente de risco
│   └── synthetic_complaints.csv (gerado)
├── output/                    # resultados (json/csv/md/html)
├── scripts/
│   ├── generate_synthetic.py
│   ├── gerar_csv.py
│   └── reclamacoes_bancarias_500.csv
└── app/
    ├── Dockerfile
    ├── requirements.txt
    └── src/
        ├── main.py            # FastAPI: /, /analyze, /analyze-form, /batch
        ├── graph.py           # LangGraph: triage → risk → report
        ├── llm.py             # cliente Bedrock + parse JSON
        ├── settings.py        # AWS + 2 modelos + paths
        ├── profanity.py
        ├── report_writer.py   # gera JSON + CSV + MD + HTML
        ├── agents/
        │   ├── triage.py      # Haiku
        │   ├── risk.py        # Sonnet + RAG
        │   └── report.py      # consolidação
        ├── rag/
        │   └── policy_loader.py
        └── templates/         # index, result, report (Jinja2)
```

## Comandos

```bash
make help               # lista alvos
make up                 # sobe o serviço
make logs               # tail dos logs (entrada/saída/tempo por agente)
make generate-data      # CSV sintético pequeno
make batch              # processa o CSV pequeno
make batch-500          # processa o CSV oficial de 500
make analyze TEXT='Fui cobrado duas vezes...'   # análise avulsa via curl
make clean              # para e remove volumes
```

## Avisos

- Dataset **exclusivamente sintético**, conforme as notas de compromisso do desafio.
- Tudo roda **localmente**; nada persistido em nuvem.
- Para evoluir para Nível 3 (guardrails Bedrock + ADR HTML + análise de custos), troque de branch:
  ```bash
  git checkout feature/level-3
  ```
