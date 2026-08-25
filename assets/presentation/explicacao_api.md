# FinGuard — Como a API funciona

## 1. O que ela faz

Recebe o texto de uma reclamação bancária (via formulário web, `POST /analyze` ou upload de CSV em `POST /batch`) e devolve um **veredito estruturado**: categoria, produto, sentimento, urgência, nível de risco, justificativa, ações recomendadas, SLA de resposta e área responsável — pronto para virar um relatório gerencial (JSON/CSV/MD/HTML) ou alimentar um painel decisório.

Não é um chatbot: é um **classificador + avaliador de risco** de ponta a ponta, com proteção de entrada/saída embutida.

## 2. Como faz — a arquitetura

Um grafo de estados (**LangGraph** — `app/src/graph.py`) encadeia 5 nós sequenciais, cada um com timing medido individualmente:

```
Guardrail Input → Triagem (Haiku) → Risco+RAG (Sonnet) → Consolidação/Overrides → Guardrail Output
```

Cada execução gera um `trace_id`, e o resultado (com `timings_ms` por etapa) é gravado num `deque` em memória (`_traces`) para alimentar `/traces` e o painel decisório — além de ser persistido em disco via `write_outputs()`.

Para lotes, `POST /batch` processa o CSV em paralelo com `ThreadPoolExecutor`, aplicando um controle **AIMD** (Additive Increase/Multiplicative Decrease, inspirado em TCP congestion control): se a taxa de `ThrottlingException` do Bedrock passa de 5%, reduz workers pela metade e aumenta o delay; se zero throttling, aumenta 1 worker e reduz o delay. Isso roda em até 3 "passes" de recuperação (`main.py:220-364`).

## 3. Elementos de IA incorporados

| Componente | Modelo/Técnica | Papel |
|---|---|---|
| **Triagem** | Claude **Haiku 4.5** (Bedrock) | Classifica categoria, produto, sentimento, urgência — tarefa simples e barata |
| **Análise de risco** | Claude **Sonnet 4.5** (Bedrock) | Avalia risco (fraude, LGPD, reputacional), com RAG |
| **RAG** | FAISS + **Titan Embed Text v2** (1024 dim) | Recupera trechos da Política Interna (POL-SAC-001) para fundamentar a decisão de risco |
| **Guardrails** | **AWS Bedrock Guardrails** (+ fallback local em regex) | Bloqueia entrada maliciosa/fora de escopo; sanitiza PII e tom na saída |

Fluxo de IA em detalhe:

- **Guardrail de entrada** (`agents/guardrail.py:104`): chama `apply_guardrail` do Bedrock (source=INPUT). Se indisponível, cai num fallback local por regex/lista de termos (prompt injection, ameaças, texto curto demais).
- **Triagem** (`agents/triage.py`): prompt de sistema rígido, com categorias/produtos/urgências fechados e **gatilhos obrigatórios de urgência** (menção a Banco Central/Procon/Justiça, indício de fraude → urgência Crítica). `temperature=0.1` para consistência.
- **Risco + RAG** (`agents/risk.py`): monta uma query com texto + dimensões da triagem, busca `k=4` chunks mais similares no índice FAISS (`rag/retriever.py`), injeta os trechos da política no prompt do Sonnet e pede JSON com nível de risco, justificativa citando a seção da POL-SAC-001, e até 5 ações recomendadas.
- **Guardrail de saída** (`agents/guardrail.py:193`): chama `apply_guardrail` (source=OUTPUT) nos campos `texto_original`, `summary`, `risk_justification` — remove PII, tom impróprio — depois roda regex locais adicionais (CPF, cartão, conta, nome) e um filtro de palavrões (`profanity.py`) como segunda camada de defesa.

## 4. Justificativa das escolhas

- **Haiku p/ triagem, Sonnet p/ risco**: classificação categórica é uma tarefa simples — usar um modelo maior seria desperdício de custo/latência. Risco exige raciocínio sobre política + contexto, onde a qualidade do modelo maior compensa.
- **RAG sobre a política interna em vez de hardcoded**: mantém a avaliação de risco auditável e atualizável (basta re-ingerir os docs em `assets/docs/`) sem re-treinar ou reescrever prompts a cada mudança de política.
- **Guardrails em duas camadas (Bedrock + regex local)**: Bedrock Guardrails cobre PII/toxicidade/prompt-attack de forma gerenciada, mas o código nunca depende cegamente dele — há fallback local caso a chamada falhe ou o guardrail não esteja configurado (`GUARDRAIL_ID` ausente), e uma segunda passada de regex específicas do domínio bancário brasileiro (CPF, conta, nome) que o guardrail genérico pode não pegar.
- **Overrides determinísticos pós-LLM** (`agents/report.py`): o LLM decide urgência/risco, mas a política POL-SAC-001 exige garantias *duras* — canal regulatório força urgência Crítica e risco mínimo Alto, risco Crítico força urgência mínima Alta. Isso é feito em código puro (não confiado ao LLM) porque são regras de compliance não-negociáveis — o LLM pode ser inconsistente, a lógica determinística não.
- **AIMD no batch**: o free tier do Bedrock tem rate limits agressivos e variáveis; um algoritmo adaptativo (em vez de um número fixo de workers) foi "descoberto empiricamente" — reage ao throttling real em vez de chutar um valor conservador demais (lento) ou agressivo demais (falha em cascata).
- **LangGraph em vez de chamadas sequenciais soltas**: dá uma representação explícita do pipeline como grafo (com roteamento condicional para o caminho "bloqueado"), facilita instrumentação uniforme de timing/logging por nó, e deixa o fluxo auditável/visualizável.
- **`deque()` sem `maxlen` para traces**: decisão simples de simplicidade — não há requisito de limite de memória neste contexto de hackathon; decisão consciente, não um esquecimento.

## 5. Fluxo passo a passo (uma reclamação)

1. **Entrada**: texto + `product_hint` opcional + `canal` chegam via `/analyze`, `/analyze-form` ou linha de um CSV em `/batch`.
2. **Guardrail Input**: Bedrock (ou fallback local) avalia o texto. Se bloqueado → grafo desvia para `step_blocked`, retorna mensagem padrão, **não chama nenhum LLM de análise** (economiza custo e evita processar conteúdo indevido).
3. **Triagem (Haiku)**: gera categoria, produto, sentimento, urgência, resumo em JSON.
4. **Risco (Sonnet + RAG)**: busca os 4 trechos mais relevantes da política interna via embedding da query (texto + dimensões da triagem), monta o prompt com esse contexto e pede nível de risco + justificativa + ações.
5. **Consolidação (`report.py`)**: aplica os 3 overrides determinísticos de POL-SAC-001, calcula SLA (`prazo_resposta`) por urgência e área responsável por produto.
6. **Guardrail Output**: sanitiza PII/tom nos campos textuais de saída (Bedrock + regex + profanidade).
7. **Persistência**: resultado vira uma entrada em `_traces` (para `/traces` e `/api/decisorio/stats`) e, quando é o fim de um lote/consulta unitária, `write_outputs()` grava JSON/CSV/MD/HTML em `output/`.
8. **Consumo**: relatórios em `/reports` → `/report/{stem}` (HTML com Chart.js), painel `/politica-decisoria`, ou consulta individual via `/api/record/{id}` (usada pelo modal compartilhado).

## 6. Perguntas que um avaliador provavelmente faria

### Sobre arquitetura e IA

- Por que dois modelos diferentes (Haiku e Sonnet) em vez de um só? *(custo/latência vs. qualidade de raciocínio)*
- Por que LangGraph e não simplesmente funções Python encadeadas? O que o grafo ganha em relação a chamadas sequenciais diretas?
- O RAG é usado só na etapa de risco — por que não na triagem também?
- Como o sistema garante que a justificativa do Sonnet realmente cita a política e não "alucina" uma seção? (a resposta honesta: não há verificação automática — é confiança no prompt + revisão humana possível via relatório)

### Sobre guardrails e segurança

- O que acontece se o Bedrock Guardrail cair (timeout/erro de API)? *(fallback local por regex — mas cobre menos casos)*
- Como o sistema lida com prompt injection dentro do texto da reclamação? *(guardrail de entrada Bedrock + lista de termos locais)*
- A sanitização de PII na saída é suficiente para conformidade LGPD, ou é só uma camada defensiva adicional?
- Por que existe uma sanitização de saída separada da de entrada — não seria mais simples sanitizar uma vez só?

### Sobre a lógica de negócio/compliance

- Por que os overrides de urgência/risco (POL-SAC-001) são feitos em código e não delegados ao LLM? *(determinismo/auditabilidade de compliance)*
- Como o sistema versiona ou audita mudanças na política interna que alimenta o RAG?
- O que acontece se o índice RAG estiver vazio (nunca ingerido)? *(o código trata: retorna lista vazia, avisa no prompt "índice vazio")*

### Sobre escalabilidade e robustez

- Como o AIMD foi calibrado — os números (`BATCH_MAX_WORKERS=2`, `BATCH_RATE_LIMIT_DELAY=1.0`) são fixos ou adaptativos entre execuções distintas?
- O que acontece com registros que falham em todos os `BATCH_MAX_PASSES`? *(entram no relatório como categoria "Erro", registrados em `failed_{stem}.json` até o último pass)*
- Por que usar `ThreadPoolExecutor` em vez de `asyncio` puro, já que a API é FastAPI (async-first)?
- O `deque()` sem limite de tamanho para traces é uma preocupação de memória em produção — como isso seria endereçado além do escopo do hackathon?

### Sobre testabilidade/observabilidade

- Como validar que a triagem é "consistente" (mencionado no prompt) — há testes de regressão sobre outputs do LLM?
- O `/traces` mostra tempo por etapa — esse dado já foi usado para otimizar algum gargalo real?
- Como se reproduz um erro de classificação específico depois do fato (dado que o LLM não é determinístico)?
