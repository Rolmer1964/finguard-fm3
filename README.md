# FinGuard — Nível 1 (Classificador Inteligente)

> Branch `feature/level-1` · Atende exclusivamente o Nível 1 do desafio Future Minds 3.
> Versões mais completas estão em `feature/level-2` (multi-agente) e `feature/level-3` (com guardrails).

Aplicação que recebe uma reclamação de cliente em texto livre e devolve **uma análise estruturada**:

- **categoria** — Cobrança Indevida · Atendimento · Fraude/Segurança · Produto/Serviço · Cancelamento · Outros
- **produto** — Cartão de Crédito · Conta Corrente · Empréstimo · Investimentos · Seguros · Não Identificado
- **sentimento** — Positivo · Neutro · Negativo · Crítico
- **urgência** — Baixa · Média · Alta · Crítica
- **resumo** — 2–3 linhas em linguagem padronizada, com palavras impróprias ofuscadas

## Como funciona

1 chamada ao Bedrock (Claude Haiku, por padrão) com um prompt bem definido. A saída JSON é validada e o resumo passa por uma sanitização de palavras impróprias.

```
┌────────────┐       ┌────────────┐       ┌──────────────┐
│   Browser  │ ────► │  FastAPI   │ ────► │ AWS Bedrock  │
│  ou curl   │       │ (1 serviço)│       │  (Claude)    │
└────────────┘       └─────┬──────┘       └──────────────┘
                           │
                           ▼
                  ./output/{json,csv,html}
```

Sem JWT, sem banco de dados, sem orquestração multi-agente, sem guardrails. **Apenas o que o Nível 1 pede.**

---

## Pré-requisitos

- Docker Desktop em execução.
- Conta AWS com acesso a Bedrock + modelo Claude Haiku habilitado na região escolhida.

## Setup

```bash
cp .env.example .env
# editar .env com AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
make up
```

Depois disso:
- UI simples em http://localhost:8000
- API REST em http://localhost:8000/classify
- Batch em http://localhost:8000/batch

## Uso

### Pela UI

Acesse http://localhost:8000, cole o texto da reclamação, clique em **Analisar** e veja o resultado.

### Pela API (chamada única)

```bash
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"text":"Já é a terceira vez que ligo pedindo o estorno..."}'
```

Resposta:
```json
{
  "categoria": "Cobrança Indevida",
  "produto": "Cartão de Crédito",
  "sentimento": "Crítico",
  "urgencia": "Alta",
  "resumo": "Cliente relata cobrança não reconhecida no cartão de crédito, com três tentativas de contato sem resolução. Ameaça escalar para Banco Central."
}
```

### Em lote (CSV → JSON + CSV + HTML)

Dois datasets disponíveis:

| Dataset | Tamanho | Como gerar/usar |
|---|---|---|
| `data/synthetic_complaints.csv` | ~50 (rápido, dev) | `make generate-data && make batch` |
| `scripts/reclamacoes_bancarias_500.csv` | 500 (oficial do desafio) | `make batch-500` |

Ou diretamente via curl:
```bash
curl -F "file=@scripts/reclamacoes_bancarias_500.csv" http://localhost:8000/batch
```

> Atenção: 500 reclamações × 1 chamada Bedrock cada = leva alguns minutos e tem custo. Para iterar no desenvolvimento, prefira o dataset menor.

---

## RAG opcional (Bedrock Embeddings + FAISS)

Coloque PDFs/MDs/TXTs de política interna em `assets/docs/`. O sistema gera um índice vetorial **incremental** (apenas arquivos novos ou alterados são re-tokenizados) e o classificador pode injetar trechos relevantes como contexto no prompt.

```bash
# 1. Coloque seus PDFs/MDs em assets/docs/
ls assets/docs/

# 2. Gere/atualize o índice (Bedrock Titan Text Embeddings v2 → FAISS)
make up                  # precisa do container rodando para chamar Bedrock
make rag-ingest          # roda dentro do container; é incremental (só novos/alterados)
make rag-status          # mostra resumo: arquivos indexados, chunks, hash

# 3. Ative no .env
echo "RAG_ENABLED=true" >> .env
make restart             # ou: make down && make up

# Próximas classificações injetam top-3 trechos da política como contexto
```

**Como funciona:**
- `assets/docs/` é o input (PDF, MD, TXT) — você coloca o que quiser
- `assets/index/` é o output (`faiss.bin` + `manifest.json`) — gitignored, regenerável
- `manifest.json` guarda hash SHA-256 de cada arquivo. Na próxima ingestão:
  - **Novo arquivo** → tokeniza + adiciona ao índice
  - **Arquivo alterado** (hash mudou) → remove os chunks antigos do FAISS e reinsere os novos
  - **Arquivo removido** → remove os chunks correspondentes do FAISS
  - **Arquivo inalterado** → pula (zero custo)

**Tier (do quadro de RAG):** 2 — *Embeddings + FAISS in-memory persistido em disco*. Para escala maior (milhares de docs), trocar FAISS por OpenSearch/pgvector ou migrar para Bedrock Knowledge Bases.

Saídas em `./output/`:
- `synthetic_complaints.json` — estrutura completa
- `synthetic_complaints.csv` — para análise em Excel/Sheets
- `synthetic_complaints.html` — relatório com gráficos (Chart.js)

Visualize o HTML: http://localhost:8000/output/synthetic_complaints.html

---

## Estrutura

```
MARCELO/
├── docker-compose.yml         # 1 serviço (app)
├── .env.example
├── Makefile
├── data/
│   └── synthetic_complaints.csv (gerado por scripts/generate_synthetic.py)
├── output/                    # resultados gerados (json/csv/html)
├── scripts/
│   └── generate_synthetic.py  # gera dataset fictício
└── app/
    ├── Dockerfile
    ├── requirements.txt
    └── src/
        ├── main.py            # FastAPI: /, /classify, /classify-form, /batch
        ├── classifier.py      # 1 chamada ao Bedrock + parse de JSON
        ├── profanity.py       # mascaramento de palavras impróprias
        ├── report_writer.py   # gera JSON + CSV + HTML
        ├── settings.py
        └── templates/         # index, result, report (Jinja2)
```

## Comandos úteis

```bash
make help             # lista alvos
make up               # sobe o serviço
make down             # para
make logs             # tail dos logs
make generate-data    # cria CSV sintético
make batch            # processa o CSV em lote
make clean            # para e remove volumes
```

## Avisos

- O dataset é **exclusivamente sintético** (gerado por `scripts/generate_synthetic.py`), conforme as notas de compromisso do desafio.
- Tudo roda **localmente**; nada é persistido em nuvem.
- Para evoluir para Nível 2 (multi-agente) ou Nível 3 (guardrails + ADR), troque de branch:
  ```bash
  git checkout feature/level-2
  git checkout feature/level-3
  ```
