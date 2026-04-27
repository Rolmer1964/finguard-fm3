Auditoria completa. Vou consolidar o relatório de bugs.                                                                                                                                                                         
                         
  🐛 Relatório de bugs por branch                                                                                                                                                                                                 
                                                                                                                                                                                                                                    🔴 CRÍTICOS (não funciona como documentado)                                                                                                                                                                                     
                                                                                                                                                                                                                                  
  L4-1: make cluster-sagemaker e make cluster-cleanup quebram (feature/level-4)

  Local: Makefile:88-93 + app/Dockerfile + docker-compose.yml

  Causa tripla:
  1. Dockerfile faz COPY src ./src — pasta scripts/ não é copiada para a imagem
  2. docker-compose.yml monta ./assets, ./output, ./data, ./docs — não monta ./scripts
  3. Mesmo se montasse, scripts/cluster_sagemaker.py:14 calcula ROOT.parent.parent esperando rodar do host (resultaria em /app/app/src dentro do container)

  Sintoma: make cluster-sagemaker retorna python: can't open file '/app/scripts/cluster_sagemaker.py'

  Fix sugerido: mover a lógica do CLI para app/src/clustering/sagemaker_cli.py (acessível como módulo) e chamar com python -m src.clustering.sagemaker_cli ...

  ---
  🟠 ALTOS (funciona mas dá problema sutil)

  ALL-1: Índice RAG fica stale após make rag-ingest (level-1, 2, 3, 4)

  Local: app/src/rag/retriever.py:15 (@lru_cache(maxsize=1))

  Causa: o make rag-ingest roda python -m src.rag.ingest num processo separado (via docker compose exec). Atualiza o índice no disco. Mas o processo do FastAPI (uvicorn) tem o VectorStore cached em memória pelo lru_cache — não
   relê do disco até o processo reiniciar.

  Sintoma: depois de make rag-ingest, novas chamadas a /analyze continuam usando o índice antigo (ou vazio se foi a primeira ingestão).

  Workaround atual: make down && make up após cada ingestão (não documentado).

  Fix sugerido: adicionar endpoint POST /rag/reload que invalida o cache:
  @app.post("/rag/reload")
  def rag_reload():
      from .rag.retriever import _store
      _store.cache_clear()
      return {"reloaded": True}
  E ajustar rag-ingest no Makefile para chamá-lo no final:
  rag-ingest:
        $(COMPOSE) exec app python -m src.rag.ingest
        @curl -s -X POST http://localhost:8000/rag/reload || true

  ---
  🟡 MÉDIOS (raros, mas podem dar dor de cabeça)

  ALL-2: Regex greedy \{.*\} no parser de JSON (todas as branches)

  Local: app/src/classifier.py:51 (level-1) e app/src/llm.py:50 (level-2/3/4)

  match = re.search(r"\{.*\}", cleaned, re.DOTALL)

  .* é greedy: se o LLM retornar {"a": 1} ... blah {"b": 2}, captura tudo de { até o último } — json.loads() falha. Cai no try/except e retorna defaults.

  Impacto: ocorre raramente (Claude segue o prompt bem), mas quando ocorre o usuário recebe "Outros"/"Baixo" sem aviso claro.

  Fix sugerido: usar regex tolerante a aninhamento ou tentativa-e-erro de parse:
  # Tenta isolar o primeiro objeto JSON balanceado
  start = cleaned.find("{")
  if start >= 0:
      depth = 0
      for i, ch in enumerate(cleaned[start:], start):
          if ch == "{": depth += 1
          elif ch == "}":
              depth -= 1
              if depth == 0:
                  cleaned = cleaned[start:i+1]
                  break

  ---
  L4-2: Jinja2 set _ = products.append(p) é frágil (feature/level-4)

  Local: app/src/templates/clusters.html.j2:74-76

  Funciona explorando que list.append muta in-place enquanto o set _ cria uma variável escopada ao loop. Depende de internals do Jinja2 que podem mudar.

  Fix sugerido: computar products_list em pipeline.py e passar como variável:
  all_products = sorted({p for dist in cross_cluster_product.values() for p in dist.keys()})
  payload["products_list"] = all_products
  Template:
  {% for p in d.products_list %}<th>{{ p }}</th>{% endfor %}

  ---
  L2/L3/L4-1: result.html.j2 (level-2) hardcoda timings keys (feature/level-2 apenas)

  Local: app/src/templates/result.html.j2:23

  Timings: triage {{ result.timings_ms.triage }}ms · risk {{ result.timings_ms.risk }}ms · report {{ result.timings_ms.report }}ms

  Em level-2 isso funciona (sempre tem os 3 nós). Em level-3+ o template foi atualizado para iterar dinamicamente. Em level-2 não tem problema porque o pipeline sempre executa todos os 3.

  Sem ação necessária — é uma inconsistência estilística, não bug.

  ---
  🟢 BAIXOS (corner cases aceitáveis para demo)

  ┌───────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────┬─────────┐
  │  ID   │                                                  Descrição                                                  │ Branch  │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ ALL-3 │ _graph = None (global) tem race em init concorrente. GIL salva mas tecnicamente não é thread-safe.          │ 2, 3, 4 │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ L4-3  │ _tmp_cluster.csv é compartilhado entre requisições concorrentes a /clusters.                                │ 4       │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ ALL-4 │ boto3.client() recriado em cada chamada (sem connection pool persistente). Custo: ~50ms a mais por chamada. │ todas   │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ L3-1  │ CONTA_RE \b\d{4,6}-?\d\b tem falsos positivos (ex: telefones).                                              │ 3, 4    │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ L3-2  │ Mensagem do guardrail vem do console AWS — se o usuário não configurou em PT-BR, sai em EN.                 │ 3, 4    │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ L3-2  │ Mensagem do guardrail vem do console AWS — se o usuário não configurou em PT-BR, sai em EN.                 │ 3, 4    │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ ALL-5 │ _redact_local() pode marcar texto literal "5000-1" (típico de números) como conta.                          │ 3, 4    │
  └───────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────┴─────────┘

  ---
  ✅ Checagens que passaram

  - Form actions ↔ endpoint paths consistentes em todas as branches
  - Nomes de campos (category/product/etc.) consistentes entre analyze() retorno → report_writer → templates
  - LangGraph state propagation com total=False permite missing keys safely
  - IndexIDMap2(IndexFlatIP) suporta add_with_ids e remove_ids corretamente
  - Embedding cache key (SHA-256 do CSV) evita colisões
  - Output dir e index dir criados via mkdir(parents=True, exist_ok=True) — startup OK mesmo sem volume
  │ ALL-5 │ _redact_local() pode marcar texto literal "5000-1" (típico de números) como conta.                          │ 3, 4    │
  └───────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────┴─────────┘

  ---
  ✅ Checagens que passaram

  - Form actions ↔ endpoint paths consistentes em todas as branches
  - Nomes de campos (category/product/etc.) consistentes entre analyze() retorno → report_writer → templates
  - LangGraph state propagation com total=False permite missing keys safely
  - IndexIDMap2(IndexFlatIP) suporta add_with_ids e remove_ids corretamente
  - Embedding cache key (SHA-256 do CSV) evita colisões
  - Output dir e index dir criados via mkdir(parents=True, exist_ok=True) — startup OK mesmo sem volume

  - Form actions ↔ endpoint paths consistentes em todas as branches
  - Nomes de campos (category/product/etc.) consistentes entre analyze() retorno → report_writer → templates
  - LangGraph state propagation com total=False permite missing keys safely
  - IndexIDMap2(IndexFlatIP) suporta add_with_ids e remove_ids corretamente
  - Embedding cache key (SHA-256 do CSV) evita colisões
  - Output dir e index dir criados via mkdir(parents=True, exist_ok=True) — startup OK mesmo sem volume
  │ L3-1  │ CONTA_RE \b\d{4,6}-?\d\b tem falsos positivos (ex: telefones).                                              │ 3, 4    │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ L3-2  │ Mensagem do guardrail vem do console AWS — se o usuário não configurou em PT-BR, sai em EN.                 │ 3, 4    │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ ALL-5 │ _redact_local() pode marcar texto literal "5000-1" (típico de números) como conta.                          │ 3, 4    │
  └───────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────┴─────────┘

  ---
  ✅ Checagens que passaram

  - Form actions ↔ endpoint paths consistentes em todas as branches
  - Nomes de campos (category/product/etc.) consistentes entre analyze() retorno → report_writer → templates
  - LangGraph state propagation com total=False permite missing keys safely
  - IndexIDMap2(IndexFlatIP) suporta add_with_ids e remove_ids corretamente
  - Embedding cache key (SHA-256 do CSV) evita colisões
  - Output dir e index dir criados via mkdir(parents=True, exist_ok=True) — startup OK mesmo sem volume
  - LangGraph state propagation com total=False permite missing keys safely
  - IndexIDMap2(IndexFlatIP) suporta add_with_ids e remove_ids corretamente
  - Embedding cache key (SHA-256 do CSV) evita colisões
  - Output dir e index dir criados via mkdir(parents=True, exist_ok=True) — startup OK mesmo sem volume
  - Embedding cache key (SHA-256 do CSV) evita colisões
  - Output dir e index dir criados via mkdir(parents=True, exist_ok=True) — startup OK mesmo sem volume
  - StaticFiles com check_dir=False tolera dir ausente
  - {% if result.blocked %} em level-3+ corretamente curto-circuita o template para o estado bloqueado
  - StaticFiles com check_dir=False tolera dir ausente
  - {% if result.blocked %} em level-3+ corretamente curto-circuita o template para o estado bloqueado
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ L3-2  │ Mensagem do guardrail vem do console AWS — se o usuário não configurou em PT-BR, sai em EN.                 │ 3, 4    │
  ├───────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────┼─────────┤
  │ ALL-5 │ _redact_local() pode marcar texto literal "5000-1" (típico de números) como conta.                          │ 3, 4    │
  └───────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────┴─────────┘

  ---
  ✅ Checagens que passaram

  - Form actions ↔ endpoint paths consistentes em todas as branches
  - Nomes de campos (category/product/etc.) consistentes entre analyze() retorno → report_writer → templates
  - LangGraph state propagation com total=False permite missing keys safely
  - IndexIDMap2(IndexFlatIP) suporta add_with_ids e remove_ids corretamente
  - Embedding cache key (SHA-256 do CSV) evita colisões
  - Output dir e index dir criados via mkdir(parents=True, exist_ok=True) — startup OK mesmo sem volume
  - StaticFiles com check_dir=False tolera dir ausente
  - {% if result.blocked %} em level-3+ corretamente curto-circuita o template para o estado bloqueado
  - Sanitização de PII em output_guard.py é determinística e não bloqueia o pipeline

  - Sanitização de PII em output_guard.py é determinística e não bloqueia o pipeline

  ---
  ---

  - Form actions ↔ endpoint paths consistentes em todas as branches
  - Nomes de campos (category/product/etc.) consistentes entre analyze() retorno → report_writer → templates
  - LangGraph state propagation com total=False permite missing keys safely
  - IndexIDMap2(IndexFlatIP) suporta add_with_ids e remove_ids corretamente
  - Embedding cache key (SHA-256 do CSV) evita colisões
  - Output dir e index dir criados via mkdir(parents=True, exist_ok=True) — startup OK mesmo sem volume
  - StaticFiles com check_dir=False tolera dir ausente
  - {% if result.blocked %} em level-3+ corretamente curto-circuita o template para o estado bloqueado
  - Sanitização de PII em output_guard.py é determinística e não bloqueia o pipeline

  ---
  Resumo executivo
  - StaticFiles com check_dir=False tolera dir ausente
  - {% if result.blocked %} em level-3+ corretamente curto-circuita o template para o estado bloqueado
  - Sanitização de PII em output_guard.py é determinística e não bloqueia o pipeline

  ---
  Resumo executivo


  ---
  Resumo executivo

  ┌────────────┬─────────┬───────────────────┬─────────────────────────────────────────────────────┐
  Resumo executivo

  ┌────────────┬─────────┬───────────────────┬─────────────────────────────────────────────────────┐
  │ Prioridade │ Quantos │  Quais branches   │                   Devo corrigir?                    │
  │ Prioridade │ Quantos │  Quais branches   │                   Devo corrigir?                    │
  ┌────────────┬─────────┬───────────────────┬─────────────────────────────────────────────────────┐
  │ Prioridade │ Quantos │  Quais branches   │                   Devo corrigir?                    │
  ├────────────┼─────────┼───────────────────┼─────────────────────────────────────────────────────┤
  │ Prioridade │ Quantos │  Quais branches   │                   Devo corrigir?                    │
  ├────────────┼─────────┼───────────────────┼─────────────────────────────────────────────────────┤
  │ 🔴 Crítico │ 1       │ level-4           │ Sim, antes de testar Level 4 com SageMaker          │
  ├────────────┼─────────┼───────────────────┼─────────────────────────────────────────────────────┤
  │ 🔴 Crítico │ 1       │ level-4           │ Sim, antes de testar Level 4 com SageMaker          │
  │ 🔴 Crítico │ 1       │ level-4           │ Sim, antes de testar Level 4 com SageMaker          │

  ---
  ✅ Checagens que passaram


  - Form actions ↔ endpoint paths consistentes em todas as branches
  - Nomes de campos (category/product/etc.) consistentes entre analyze() retorno → report_writer → templates
  - LangGraph state propagation com total=False permite missing keys safely
  - IndexIDMap2(IndexFlatIP) suporta add_with_ids e remove_ids corretamente
  - Embedding cache key (SHA-256 do CSV) evita colisões
  - Output dir e index dir criados via mkdir(parents=True, exist_ok=True) — startup OK mesmo sem volume
  - StaticFiles com check_dir=False tolera dir ausente
  - {% if result.blocked %} em level-3+ corretamente curto-circuita o template para o estado bloqueado
  - Sanitização de PII em output_guard.py é determinística e não bloqueia o pipeline

  ---
  Resumo executivo

  ┌────────────┬─────────┬───────────────────┬─────────────────────────────────────────────────────┐
  │ Prioridade │ Quantos │  Quais branches   │                   Devo corrigir?                    │
  ├────────────┼─────────┼───────────────────┼─────────────────────────────────────────────────────┤
  │ 🔴 Crítico │ 1       │ level-4           │ Sim, antes de testar Level 4 com SageMaker          │
  ├────────────┼─────────┼───────────────────┼─────────────────────────────────────────────────────┤
  │ 🟠 Alto    │ 1       │ levels 1, 2, 3, 4 │ Sim, vai te morder no primeiro teste com rag-ingest │
  ├────────────┼─────────┼───────────────────┼─────────────────────────────────────────────────────┤
  │ 🟡 Médio   │ 2       │ várias            │ Opcional — cosmético/raro                           │
  ├────────────┼─────────┼───────────────────┼─────────────────────────────────────────────────────┤
  │ 🟢 Baixo   │ 6       │ várias            │ Aceitável para demo                                 │
  └────────────┴─────────┴───────────────────┴─────────────────────────────────────────────────────┘

  Quer que eu corrija os 2 críticos/altos agora (cluster-sagemaker em level-4 + rag-stale em todos)? São ~30 minutos de trabalho. Os médios/baixos podem ficar para depois sem prejuízo de testar.
