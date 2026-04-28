# FinGuard — Instruções para Claude Code

## Diretrizes de comportamento (Karpathy)

> Estas regras têm precedência sobre qualquer padrão default. Aplique sempre.

### 1. Pense antes de codar

- Declare suas suposições explicitamente. Se incerto, pergunte.
- Se houver múltiplas interpretações, apresente-as — não escolha silenciosamente.
- Se existir abordagem mais simples, diga. Questione quando necessário.
- Se algo não estiver claro, pare. Nomeie a confusão. Pergunte.

### 2. Simplicidade primeiro

- Mínimo de código que resolve o problema. Nada especulativo.
- Sem features além do solicitado.
- Sem abstrações para código de uso único.
- Sem "flexibilidade" ou "configurabilidade" não pedidas.
- Sem tratamento de erros para cenários impossíveis.

### 3. Mudanças cirúrgicas

- Toque apenas o que precisa ser tocado.
- Não "melhore" código adjacente, comentários ou formatação.
- Não refatore o que não está quebrado.
- Mantenha o estilo existente, mesmo que faria diferente.
- Se notar código morto não relacionado, mencione — não delete.
- Remova apenas imports/variáveis/funções que **suas** mudanças tornaram órfãos.

### 4. Execução orientada a objetivo

- Transforme tarefas em critérios verificáveis antes de implementar.
- Para tarefas de múltiplos passos, declare um plano breve.
- Perguntas de clarificação vêm **antes** da implementação, nunca depois de erros.

---

## Projeto: FinGuard

Hackathon **Future Minds 3 — Nível 3 — Grupo 23TB**.
Sistema de análise de reclamações bancárias via AWS Bedrock com pipeline de IA,
guardrails de conteúdo, RAG sobre política interna e processamento em batch paralelo.

### Stack

- **Runtime**: Python 3.12, FastAPI, Docker Compose
- **IA**: AWS Bedrock — Claude Haiku 4.5 (triagem) + Claude Sonnet 4.5 (risco + RAG)
- **Guardrails**: AWS Bedrock Guardrails (ID configurável via `.env`)
- **RAG**: FAISS + Amazon Titan Embed Text v2 (1024 dim)
- **Templates**: Jinja2 + Chart.js (relatórios HTML interativos)
- **Configuração**: Pydantic Settings carregada de `.env`

### Estrutura de pastas

```
app/src/
  main.py            # FastAPI app, rotas, loop AIMD de batch
  graph.py           # Pipeline LangGraph, trace store (deque sem limite)
  report_writer.py   # write_outputs() — gera JSON/CSV/MD/HTML
  settings.py        # Pydantic Settings (lê do .env)
  templates/
    index.html.j2    # Formulário de envio individual
    report.html.j2   # Relatório gerencial de batch
    reports.html.j2  # Listagem de relatórios gerados
    traces.html.j2   # Log de execuções com estatísticas
    result.html.j2   # Resultado de registro individual
    admin.html.j2    # Painel de admin (rebuild RAG index)
    _modal.html.j2   # Modal compartilhado (incluído via {% include %})

assets/
  docs/              # PDFs/MDs com política interna (fonte do RAG)
  index/             # FAISS index + manifest (persistido)
  adr.html           # Architecture Decision Record
  presentation/      # Material de apresentação do hackathon
    analise_aimd.html
    proximos_passos_aimd.md
    relatorios/      # Relatórios e logs dos experimentos

output/              # Relatórios gerados em runtime (GITIGNORED)
scripts/             # CSVs de datasets de teste
documentacao/        # Docs de referência (regras.md, etc.)
```

### Comandos frequentes

```bash
# Subir o sistema
docker compose up --build

# Acompanhar logs e salvar (para análise posterior)
docker compose logs -f app | tee assets/presentation/relatorios/batch_$(date +%Y%m%d_%H%M%S).log

# Rebuild do índice RAG
curl -X POST http://localhost:8000/admin/rebuild-index
```

### Pipeline de processamento

```
Guardrail Input → [Haiku: Triagem] → [Sonnet: Risco + RAG] → Guardrail Output
```

- Registros **bloqueados** pelo guardrail: `category = "Bloqueado"`, excluídos das
  estatísticas de triagem/risco/sentimento/produto mas contados em categoria e canal.
- Timings em `timings_ms`: `guardrail_input`, `triage`, `risk`, `report`, `guardrail_output`.
- `total_ms` inclui **todos** os cinco componentes.

### Batch paralelo com AIMD

Parâmetros no `.env` (descobertos empiricamente no free tier AWS):

```
BATCH_MAX_WORKERS=2       # workers paralelos
BATCH_RATE_LIMIT_DELAY=1.0  # delay (s) entre registros por worker
BATCH_MAX_RETRIES=2       # tentativas por worker antes de escalar
BATCH_MAX_PASSES=3        # passes de recuperação (multi-pass)
BATCH_RETRY_DELAY=15.0    # espera base entre passes (× 1 + throttle_rate)
```

**AIMD**: ao detectar `ThrottlingException` com taxa > 5%, aplica
`workers // 2` e `delay += 1.0s`. Com throttle == 0, aplica `workers + 1`
e `delay -= 0.5s`. O algoritmo persiste entre passes dentro de um batch.

### Convenções

- **Timezone**: UTC-3 (BRT). Constante `_TZ_BRT = timezone(timedelta(hours=-3))` em `main.py`.
- **Stems de relatório**: `report_YYYY-MM-DD-HH-MM-SS` (horário BRT).
- **`output/`** é gitignored — artefatos de runtime não são versionados.
- **`assets/presentation/relatorios/`** guarda os relatórios de experimento versionados.
- **Commits**: nunca incluir `Co-Authored-By`.
- **Linguagem**: respostas sempre em Português Brasil.

### Endpoints principais

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Formulário individual |
| POST | `/analyze` | Processa um registro |
| POST | `/batch` | Processa CSV em batch |
| GET | `/reports` | Lista relatórios gerados |
| GET | `/traces` | Log de execuções + estatísticas |
| GET | `/output/{filename}` | Serve arquivos de output |
| GET | `/api/record/{id}` | Retorna registro por ID (usado pelo modal) |
| POST | `/ingest` | Dispara re-ingestão RAG em background |
| GET  | `/ingest/status` | Estado atual da ingestão |

### Decisões de arquitetura

Ver `assets/adr.html` para o registro completo. Decisões-chave:

- **Haiku para triagem, Sonnet para risco**: otimização de custo — classificação simples
  não justifica modelo maior.
- **Multi-pass com AIMD**: recuperação de throttling sem intervenção manual, inspirado no
  controle de congestionamento TCP.
- **Modal compartilhado via `_modal.html.j2`**: elimina duplicação entre relatório e traces;
  usa `INDEX[id]` local quando disponível, fallback para `GET /api/record/{id}`.
- **`deque()` sem maxlen**: log de execuções sem limite de registros em memória.
