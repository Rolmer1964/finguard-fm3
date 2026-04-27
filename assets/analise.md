● LangGraph + Bedrock Runtime (o que usamos)                                                                                                                                                                                      
  
  O que é: dois componentes separados.                                                                                                                                                                                                                                                                                                                                                                                                                              
  - LangGraph = biblioteca Python open source (do time LangChain) para orquestrar fluxos com agentes. Você descreve o pipeline como um grafo de nós (cada nó é uma função Python) e LangGraph cuida do estado entre eles.           - Bedrock Runtime = a API mais básica do Bedrock. Recebe um prompt, devolve uma resposta. Sem orquestração, sem ferramentas, sem memória — só "manda texto, recebe texto".                                                                                                                                                                                                                                                                                          Como funciona na prática:                                                                                                                                                                                                                                                                                                                                                                                                                                           # 1. Você define cada agente como uma função Python normal                                                                                                                                                                        def triage_node(state):                                                                                                                                                                                                               client = boto3.client("bedrock-runtime")                                                                                                                                                                                    
      resp = client.invoke_model(
          modelId="anthropic.claude-3-haiku-20240307-v1:0",
          body=json.dumps({
              "anthropic_version": "bedrock-2023-05-31",
              "messages": [{"role": "user", "content": state["text"]}],
          })
      )
      return {"triage": parse(resp)}

  # 2. Você desenha o grafo explicitamente
  g = StateGraph(State)
  g.add_node("triage", triage_node)
  g.add_node("risk", risk_node)
  g.add_node("report", report_node)
  g.set_entry_point("triage")
  g.add_edge("triage", "risk")
  g.add_edge("risk", "report")

  # 3. Roda local, no seu container
  app = g.compile()
  result = app.invoke({"text": "..."})

  Quem decide a ordem das chamadas: você, no código.
  Onde roda: seu Docker, sua máquina, qualquer cloud.
  Custo: apenas os tokens consumidos por cada invoke_model.

  ---
  Bedrock Agents (serviço gerenciado AWS)

  O que é: um produto da AWS onde você configura um agente no console (ou via API) e a AWS cuida da orquestração.

  Componentes que você configura na AWS:

  1. Foundation Model — qual Claude/Llama o agente usa para raciocinar
  2. Instructions — system prompt do agente ("Você é um analista bancário…")
  3. Action Groups — "ferramentas" que o agente pode chamar. Cada Action Group é definido por um schema OpenAPI apontando para um AWS Lambda que executa a lógica. Ex.: validar_cpf(), consultar_score().
  4. Knowledge Bases — RAG gerenciado. Você joga PDFs/MDs num bucket S3 e a AWS cria embeddings, indexa em OpenSearch/Pinecone/Aurora e o agente consulta automaticamente.
  5. Guardrails — opcional, anexa o guardrail Bedrock.

  Como funciona na prática:

  # Você não escreve graph nenhum. Apenas invoca o agente:
  client = boto3.client("bedrock-agent-runtime")
  resp = client.invoke_agent(
      agentId="ABC123XYZ",          # criado no console
      agentAliasId="TSTALIASID",
      sessionId="reclamacao-42",
      inputText="Fui cobrado duas vezes na fatura..."
  )
  # AWS internamente:
  #   1. LLM raciocina sobre o input
  #   2. Decide chamar a Knowledge Base "politica_interna" (RAG)
  #   3. Decide chamar o Action Group "validar_padrao_fraude" (Lambda)
  #   4. Recebe resultado, raciocina mais
  #   5. Sintetiza resposta final
  # Você só vê: o trace dos passos + a resposta final.

  Quem decide a ordem das chamadas: a própria AWS, com base no raciocínio do LLM (estilo ReAct: Reason → Act → Observe → Reason…).
  Onde roda: AWS, sempre.
  Custo: tokens do LLM + execução de Lambdas + Knowledge Base (cobra por consulta + storage do vector DB).

  ---
  Comparação direta

  ┌─────────────────────────────────────┬──────────────────────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────────────────────┐
  │               Aspecto               │                       LangGraph + Runtime                        │                                Bedrock Agents                                │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Onde a lógica de orquestração mora  │ Seu código Python (graph.py)                                     │ Console AWS / configuração do agente                                         │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Quem decide qual agente roda quando │ Você, no grafo                                                   │ A AWS, dinamicamente, baseada no raciocínio do LLM                           │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Multi-step reasoning                │ Explícito (você desenha cada aresta)                             │ Implícito (loop ReAct gerenciado pela AWS)                                   │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Ferramentas (functions/tools)       │ Funções Python normais que você importa                          │ Action Groups com schema OpenAPI + Lambda                                    │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ RAG                                 │ Você implementa (FAISS, Chroma, txt em memória, etc.)            │ Knowledge Base gerenciado (S3 → OpenSearch/Pinecone)                         │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Versionamento                       │ Git                                                              │ Versions/Aliases no console                                                  │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Debugging                           │ Logs locais, breakpoints, prints                                 │ CloudWatch + Trace UI no console AWS                                         │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Lock-in                             │ Nenhum (pode trocar Bedrock por OpenAI/Ollama mudando 1 arquivo) │ Total (amarrado a Lambda + S3 + OpenSearch + IAM)                            │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Time-to-deploy local                │ docker compose up                                                │ Precisa: conta AWS + IAM roles + Lambda deployadas + Knowledge Base indexada │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Custo extra além dos tokens         │ Zero                                                             │ Lambda invocations + Knowledge Base queries + storage                        │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Comportamento determinístico        │ Alto (mesmo input → mesma sequência de nós)                      │ Médio (LLM decide o caminho — pode variar)                                   │
  ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Quando brilha                       │ Pipelines bem definidos, controle total, multi-cloud, dev local  │ Chatbots multi-turn, raciocínio dinâmico, integração nativa com AWS          │
  └─────────────────────────────────────┴──────────────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────────┘

  ---
  Por que LangGraph encaixa melhor no nosso caso

  Para análise de reclamação, a sequência é fixa e bem conhecida: triagem → risco → relatório. Sempre nessa ordem, sempre os 3 passos. Não precisamos de um LLM "decidindo se vai consultar a política" — sabemos que vai. Esse é 
  o caso clássico de orquestração explícita > orquestração agêntica:

  - Previsibilidade: você lê o graph.py e sabe exatamente o que acontece. Com Bedrock Agents, o LLM pode "decidir" pular um passo num caso de borda — péssimo para auditoria de compliance.
  - Custo: Bedrock Agents faz 1 chamada extra de "raciocínio" antes de cada Action Group (overhead de tokens). LangGraph chama só o que você marcou.
  - Local-first: o desafio pede execução local. LangGraph + Runtime roda 100% no seu container. Bedrock Agents exige Lambdas deployadas na AWS para os Action Groups.
  - Karpathy-friendly: menos abstração, menos magia. Cada agente é uma função, cada transição é uma linha do add_edge.

  ---
  Bedrock Agents brilharia se…

  - A reclamação pudesse ter caminhos muito diferentes (ex.: "se for fraude, chama API X; se for cobrança, chama API Y; se for atendimento, ignora") e quiséssemos que o LLM decidisse isso sozinho.
  - Já tivéssemos várias APIs internas (consulta de score, blacklist, histórico) e quiséssemos um agente conversacional que escolhe quais usar.
  - Estivéssemos construindo um chatbot multi-turn com memória, em vez de um pipeline batch.

  Para FinGuard, o pipeline é linear e auditável. Por isso LangGraph + Runtime é melhor.

  ---
  TL;DR:
  - LangGraph + Runtime = você escreve um pipeline Python explícito; cada nó faz uma chamada Bedrock simples.
  - Bedrock Agents = você descreve um agente na AWS e a AWS orquestra dinamicamente; bom quando o raciocínio dinâmico vale o lock-in.
