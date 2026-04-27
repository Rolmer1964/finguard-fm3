Com o Amazon Bedrock, você pode acessar facilmente modelos de IA pré-treinados por meio de simples chamadas de API para gerar texto, resumir conteúdo ou responder perguntas.

## Comparação com Abordagens Tradicionais de IA
Os Modelos de Base representam uma mudança fundamental em relação aos sistemas de IA convencionais. As abordagens tradicionais de IA - incluindo sistemas baseados em regras, modelos de aprendizado supervisionado e aplicações de IA específicas - são projetadas para tarefas específicas como detecção de spam em e-mails ou classificação de imagens. Cada modelo tradicional serve a um único propósito, exigindo modelos separados para diferentes tarefas como reconhecimento de imagem, análise de sentimento ou reconhecimento de fala, cada um treinado em conjuntos de dados restritos e específicos para a tarefa.

Essa abordagem tradicional resulta em adaptabilidade limitada, pois os modelos não conseguem aplicar seu conhecimento além do seu caso de uso específico. Os Modelos de Base quebram essa limitação ao oferecer versatilidade e adaptabilidade sem precedentes, marcando uma evolução significativa na forma como os sistemas de IA são projetados e implantados.

Em sua essência, os Modelos de Base utilizam uma das três principais arquiteturas de transformers, cada uma projetada para tipos específicos de tarefas. Modelos apenas com codificador se destacam na compreensão e análise de dados de entrada. Esses modelos transformam texto, imagens ou outras entradas em representações matemáticas chamadas incorporações, tornando-os particularmente eficazes para tarefas como busca semântica e classificação. Modelos codificador-decodificador combinam capacidades de compreensão e geração, tornando-os ideais para tarefas como tradução e resumo. Finalmente, modelos apenas com decodificador se especializam na geração de novo conteúdo e se tornaram a arquitetura mais comum para grandes modelos de linguagem.

### Resumo
A evolução da IA e do Machine Learning, culminando nos Modelos de Base, representa uma mudança transformadora na tecnologia moderna de inteligência artificial, abrangendo tanto as capacidades de resolução de problemas semelhantes às humanas da IA tradicional quanto o foco do ML no reconhecimento de padrões por meio de várias abordagens de aprendizado. Os Modelos de Base transcendem as limitações convencionais ao criar sistemas versáteis capazes de lidar com múltiplas tarefas com treinamento adicional mínimo, usando arquiteturas de transformadores que processam informações em paralelo e demonstram habilidades emergentes. Esses modelos democratizaram capacidades avançadas de IA em setores como saúde, finanças e desenvolvimento de software, oferecendo também aprendizado por transferência que permite a aplicação de conhecimento em diferentes domínios com menos dados e tempo de treinamento. Diferentemente dos modelos tradicionais que exigem sistemas separados para diferentes tarefas, os Modelos de Base podem adaptar seu amplo entendimento em várias aplicações, embora enfrentem desafios como custos computacionais e possível viés. O futuro dessa tecnologia aponta para AGI, AutoML, IA de Borda e IA Explicável, enfatizando o desenvolvimento responsável e aplicações práticas para resolução de problemas complexos do mundo real, marcando um passo significativo em direção a uma inteligência artificial mais generalizada.

## Aplicações de IA
Esta seção descreve as principais aplicações de IA e seus usos específicos por indústria. Essas aplicações de IA visam:

- Melhorar as experiências dos clientes
- Aumentar a produtividade dos funcionários
- Melhorar as operações de negócios

## Aplicações na indústria
O atendimento ao cliente é outra área onde os Modelos de Base estão causando um impacto significativo. Eles estão impulsionando chatbots mais inteligentes e sensíveis ao contexto, automatizando respostas de e-mail e classificação de tickets, e aprimorando assistentes de voz para interações mais naturais. Isso está levando a experiências de cliente aprimoradas e operações de atendimento ao cliente mais eficientes

### Resumo
As aplicações de IA estão revolucionando as indústrias, cada uma servindo para melhorar as experiências dos clientes, aumentar a produtividade e aprimorar as operações. A Visão Computacional permite que máquinas compreendam informações visuais, exemplificada por tecnologias como o Stable Diffusion no Amazon Bedrock, que transforma descrições textuais em imagens e encontra aplicações em veículos autônomos, imagens médicas e sistemas de segurança. O PLN facilita a comunicação humano-computador por meio de tecnologias como a Amazon Alexa, alimentando aplicações em atendimento ao cliente, análise de documentos de seguros e sistemas de suporte educacional, efetivamente conectando a comunicação entre humanos e máquinas. O processamento de documentos inteligente combina várias tecnologias de IA para processar e digitalizar documentos automaticamente em diversos setores, desde bancos e serviços jurídicos até saúde, transformando documentos físicos em informações digitais pesquisáveis para maior eficiência. Os sistemas de Detecção de Fraude empregam IA e machine learning para monitorar continuamente transações e atividades em busca de padrões suspeitos, protegendo transações financeiras, plataformas de e-commerce e sistemas de saúde ao identificar e prevenir atividades fraudulentas em tempo real.

## FM = Foundation Models

Os Foundation Models (FMs) são modelos de inteligência artificial de grande escala que foram pré-treinados em vastas quantidades de dados e podem ser adaptados para diversas tarefas. No Amazon Bedrock, esses modelos incluem:

- Modelos de linguagem (como Claude da Anthropic, Llama da Meta, modelos da AI21 Labs)
- Modelos de geração de imagens (como Stable Diffusion)
- Modelos de embedding para busca semântica

A grande vantagem dos FMs é que eles já vêm com conhecimento geral pré-treinado, e você pode:

- Usá-los diretamente via API
- Personalizá-los com técnicas como fine-tuning
- Aumentar suas capacidades com RAG (Retrieval Augmented Generation)
- Criar agentes que executam tarefas específicas

Isso elimina a necessidade de treinar modelos do zero, tornando o desenvolvimento de aplicações com IA generativa muito mais acessível e rápido.

Existem cinco principais razões para usar o Amazon Bedrock na criação de aplicações de IA generativa.

- Flexibilidade na escolha do modelo
- Fácil personalização do modelo com seus próprios dados
- Agentes totalmente gerenciados para executar tarefas
- Integração de Geração Aumentada via Recuperação (RAG) com seus próprios dados
- Fácil avaliação e teste de modelos

O Amazon Bedrock oferece uma ampla gama de modelos de base de alto desempenho da Amazon e de empresas líderes como Anthropic, Meta, AI21 Labs, Cohere, Mistral AI e Stability AI, com mais por vir em breve. O Amazon Bedrock fornece modelos com suporte multimodal, o que significa que você pode usá-lo para uma variedade de casos de uso para gerar texto, imagens e vídeo.

A tabela abaixo lista informações sobre modelos de fundação suportados pelo Amazon Bedrock. A lista a seguir descreve as colunas na tabela:

- Provedor — O fornecedor do modelo.
- Modelo — O nome do modelo de fundação.
- ID do modelo — A ID AWS independente da região do modelo. Usado em operações de inferência.
- Suporte ao modelo de região única — As AWS regiões que oferecem suporte a chamadas de inferência para o modelo nessa única região. Para obter mais informações, consulte Envie prompts e gere respostas com a inferência de modelo.
- Suporte ao perfil de inferência entre regiões — As AWS regiões que oferecem suporte a chamadas de inferência para várias regiões dentro da mesma área geográfica. Para obter mais informações, consulte Regiões e modelos que compatíveis com perfis de inferência.
- Modalidades de entrada — As modalidades que podem ser fornecidas como entrada para o modelo em inferência.
- Modalidades de saída — As modalidades que podem ser produzidas a partir do modelo em inferência.
- Streaming — Se o modelo suporta operações de streaming, como InvokeModelWithResponseStreamConverseStreame.
- Parâmetros de inferência — Um link para os parâmetros de inferência que você pode especificar ao invocar o modelo.

## Personalização de modelo
Muitas vezes, o uso dos modelos de base fornece conhecimento para uma variedade de casos de uso. Para experiências de usuário e tarefas personalizadas e diferenciadas, você pode optar por ajustar modelos de base usando seu próprio conjunto de dados. Esse processo tradicionalmente requer habilidades especializadas e código personalizado. Com o Amazon Bedrock, você pode personalizar FMs de forma privada com seus dados por meio de uma interface visual e sem precisar escrever código. Basta fornecer os conjuntos de dados no Amazon Simple Storage Service (Amazon S3) e, opcionalmente, ajustar os hiperparâmetros para treinar seu modelo personalizado, que pode então ser invocado pelo Amazon Bedrock da mesma maneira que outros modelos.

O Amazon Bedrock faz uma cópia separada do FM original e a disponibiliza apenas para você, mantendo seus dados seguros e indisponíveis para provedores de modelos e outros.

Geração aumentada via recuperação (RAG)

A geração aumentada via recuperação (RAG) é uma técnica usada para melhorar as respostas do modelo de base, tornando-as mais relevantes para seus dados específicos e fornecendo informações adicionais que o modelo de base ainda não possui. Essa técnica é usada em vez de ter que retreinar o modelo várias vezes para incluir novos dados. Isso é útil em casos onde você precisa de informações atualizadas, incluir informações proprietárias da organização ou incluir dados de um domínio específico.

- User Query - O usuário faz uma pergunta/consulta (representada pelo ícone de lupa)
- Amazon Bedrock - A consulta é enviada para o Amazon Bedrock (representado pelo ícone do cérebro/IA)
- Amazon Bedrock Knowledge Bases - O Bedrock acessa sua base de conhecimento (círculo roxo central)
- Augmented Prompt - O prompt é enriquecido com informações relevantes recuperadas da base de conhecimento
- Modelos de IA - O prompt aumentado é enviado para um dos modelos disponíveis:
     - Meta Llama
     - Anthropic Claude
- Answer - A resposta final é gerada e entregue ao usuário (ícone de check)

## Infraestrutura Operacional

## Provisionamento de modelo

O provisionamento de modelos no Amazon Bedrock oferece opções flexíveis para atender a diversas demandas de carga de trabalho. O serviço inclui um recurso de Capacidade Reservada, permitindo que as organizações garantam recursos computacionais dedicados para suas workloads de IA. Isso assegura desempenho e disponibilidade consistentes, especialmente para aplicações essenciais para a operação ou durante períodos de alta demanda. O sistema de provisionamento suporta scaling dinâmico, ajustando automaticamente os recursos com base nos padrões de uso para otimizar custo e desempenho. As organizações podem definir políticas de provisionamento personalizadas, equilibrando fatores como tempo de resposta, throughput e eficiência de custos.

Além do provisionamento da infraestrutura, o Amazon Bedrock oferece recursos que melhoram a experiência do usuário, sendo o Response Streaming um exemplo fundamental.

## Streaming de Respostas
O Streaming de Respostas é um recurso fundamental que aprimora a capacidade de resposta e a experiência do usuário em aplicações de IA criadas no Amazon Bedrock. Essa capacidade permite a transmissão em tempo real das saídas do modelo à medida que são geradas, em vez de esperar que toda a resposta seja concluída. Para aplicações como chatbots ou ferramentas de geração de conteúdo, isso resulta em interações mais naturais e envolventes.

Enquanto o Streaming de Respostas aprimora as interações em tempo real, o Fluxo de Prompts eleva o desenvolvimento de aplicações de IA a um novo patamar, permitindo fluxos de trabalho complexos e de várias etapas.

## Fluxo de prompt
O Fluxo de prompt no Amazon Bedrock fornece uma sofisticada camada de orquestração para interações complexas de IA. O recurso permite que desenvolvedores projetem, testem e implantem fluxos de trabalho de IA de várias etapas por meio de uma interface visual intuitiva. As organizações podem criar pipelines de processamento dinâmicos que combinam vários modelos, incorporam lógica de negócios e lidam com árvores de decisão complexas. O construtor de fluxo de trabalho visual simplifica a criação de aplicações sofisticadas de IA, enquanto as ferramentas integradas de teste e validação garantem confiabilidade em cada etapa. O Fluxo de prompt suporta recursos avançados como ramificação condicional, tratamento de erros e gerenciamento de estado, tornando possível criar aplicações de nível de produção que podem se adaptar a entradas e cenários variados.

À medida que as organizações constroem fluxos de trabalho de IA mais sofisticados, garantir o uso responsável e em conformidade da IA torna-se crucial. É aqui que as barreiras de proteção entram em jogo.

## Barreiras de proteção
As barreiras de proteção permitem que as organizações definam e apliquem políticas que governam o comportamento do modelo de IA. As organizações podem implementar filtragem de conteúdo, estabelecer limites éticos e garantir a conformidade com requisitos regulatórios em todas as interações de IA. A estrutura de barreiras de proteção inclui recursos sofisticados de correspondência de padrões e análise de conteúdo, permitindo um controle granular sobre as saídas do modelo.

Com a segurança e a governança implementadas, as organizações podem se concentrar na adaptação dos modelos de IA às suas necessidades específicas.

## Capacidades avançadas do modelo

## Modelos de Incorporação Vetorial
Os Modelos de Incorporação Vetorial fornecem capacidades essenciais para trabalhar com dados não estruturados e permitir aplicações de busca semântica. Esses modelos transformam texto, imagens e outros tipos de dados em representações vetoriais de alta dimensão – essencialmente, listas de números que capturam o significado semântico dos dados. O Amazon Bedrock oferece modelos de incorporação especializados que realizam essa conversão de forma eficiente. As incorporações resultantes permitem que os sistemas de IA compreendam e comparem conteúdo com base no significado, e não apenas em correspondências exatas, possibilitando buscas e análises sofisticadas por similaridade.

A integração com bancos de dados vetoriais populares e mecanismos de busca permite que as organizações construam sistemas poderosos de busca e recomendação que entendem contexto e relevância. As capacidades de incorporação do Amazon Bedrock suportam múltiplos idiomas e domínios, tornando-os ferramentas versáteis para várias aplicações de IA.

Com base nessas representações vetoriais, a geração aumentada via recuperação (RAG) combina o poder dos Modelos de Base com o conhecimento específico da organização.

## Geração aumentada via recuperação (RAG)
A geração aumentada via recuperação (RAG) representa um poderoso paradigma para combinar o conhecimento dos Modelos de Base com informações específicas da organização. O Amazon Bedrock fornece suporte abrangente para implementações de RAG, incluindo ferramentas para processamento de documentos, fragmentação e indexação semântica. As capacidades de RAG da plataforma se integram perfeitamente com Bases de Conhecimento e Incorporações Vetoriais, permitindo a recuperação inteligente de informações e incorporação nas respostas do modelo.

À medida que as organizações aproveitam o RAG para respostas aprimoradas, o ajuste fino da saída torna-se crítico, e é aí que os Parâmetros de Inferência do Modelo entram em jogo.

## Parâmetros de Inferência do Modelo
Os Parâmetros de Inferência de Modelo fornecem controle detalhado sobre como os Modelos de Base geram respostas. As organizações podem ajustar parâmetros como temperatura, amostragem top-p e comprimento máximo de token para otimizar as saídas do modelo para diferentes cenários. A plataforma inclui ferramentas para experimentação e otimização de parâmetros, ajudando as organizações a encontrar o equilíbrio certo entre criatividade e consistência nas respostas do modelo.

À medida que as organizações refinam as saídas de seus modelos por meio do ajuste de parâmetros, garantir um desempenho consistente durante as atualizações torna-se crucial. É aí que entra o Model Shadowing.

## Resumo
Em conclusão, o Amazon Bedrock fornece um conjunto abrangente de recursos que abordam todos os aspectos da implantação de IA empresarial. Desde a seleção e personalização de modelos até segurança, monitoramento e gerenciamento operacional, a plataforma oferece as ferramentas e capacidades necessárias para criar e operar aplicações sofisticadas de IA em escala. A evolução contínua desses recursos, combinada com o compromisso da Amazon com segurança e confiabilidade, garante que as organizações possam construir suas estratégias de IA com confiança sobre a base do Amazon Bedrock.

## Seleção de Modelo de Base

## Visão geral
Selecionar o modelo de base certo é uma etapa importante para criar aplicações robustas de IA generativa adaptadas às suas necessidades específicas. Com o Amazon Bedrock, você pode aproveitar modelos de base (FMs) poderosos para uma variedade de casos de uso, como compreensão de linguagem natural, geração de imagens, resumo de texto e até mesmo conclusão de código. 

Compreender as características e aplicações ideais de cada modelo ajudará você a tomar decisões informadas que maximizem a eficácia de suas soluções de IA generativa. Para obter uma lista de casos de uso de IA generativa, visite o explorador de casos de uso.

A seguir estão os principais fatores a serem considerados ao escolher seu modelo ou modelos. Seja você estiver procurando gerar texto semelhante ao humano, criar imagens atraentes, extrair insights de documentos ou criar agentes conversacionais, o Amazon Bedrock oferece modelos adaptados ao seu caso de uso específico.

- Capacidades e especializações do modelo
- Modalidades de entrada/saída
- Tamanho da janela de contexto
- Precisão
- Características de desempenho
- Eficiência de custo
- Recursos de IA responsável
- Requisitos específicos do caso de uso

## Critérios de Seleção de Modelo de Base

## Capacidades do modelo
O primeiro passo para selecionar um modelo de base (FM) é restringir seu caso de uso por capacidades gerais do modelo, como a modalidade do modelo. Modalidades são categorias de conteúdo que o FM é capaz de entender ou gerar. Exemplos de modalidade incluem:

- Áudio
- Incorporação
- Imagem
- Multimodal
- Fala
- Texto
- Visão de Texto
- Vídeo

Cada modelo de base tem seus pontos fortes, e entender as capacidades do modelo é uma etapa importante nos critérios de seleção.

- Habilidades de raciocínio
    > Modelos como a família Claude da Anthropic se destacam em raciocínio complexo, instruções com nuances e manutenção de contexto em conversas.
- Geração criativa
    > Alguns modelos são melhores para escrita criativa, narrativas ou geração de textos de marketing.
- Conhecimento factual
    > Considere a importância da precisão factual para o seu caso de uso. Os modelos têm diferentes datas de corte de conhecimento e níveis variados de confiabilidade factual.
- Conhecimento do domínio
    > Alguns modelos têm melhor desempenho em domínios específicos como saúde, finanças ou conteúdo jurídico devido aos seus dados de treinamento.

## Modalidades de Entrada/Saída
Os modelos de base suportam diferentes tipos de modalidade de entrada e saída, o que impacta diretamente o que sua aplicação pode fazer. O que considerar:

- Modelos apenas de texto
    > Modelos como o Amazon Nova Micro trabalham exclusivamente com entradas e saídas de texto.

- Modelos de geração de imagens
    > O Stable Diffusion da Stability AI e o Amazon Nova Canvas criam imagens a partir de descrições textuais.

- Modelos multimodais
    > Modelos como o Claude Sonnet 4 podem processar tanto texto quanto imagens como entrada, permitindo a compreensão de imagens e o raciocínio sobre conteúdo visual.

Aplicação prática: Se sua aplicação precisa analisar documentos com gráficos e imagens, escolha um modelo multimodal. Se você está construindo uma aplicação de geração de imagens a partir de texto, o Stable Diffusion ou o Amazon Nova Canvas seriam escolhas apropriadas.

## Janela de Contexto
A janela de contexto representa a quantidade de informações que um modelo pode processar em uma única solicitação, medida em tokens. Um token é composto por alguns caracteres de texto e é a unidade básica de entrada/saída para modelos de base. Fornecer contexto adicional na solicitação, como uma imagem, um vídeo ou fornecer informações contextuais por meio de geração aumentada via recuperação conta como tokens utilizados. O que considerar:

- Janelas de contexto curtas (2 mil a 32 mil tokens)
    > Adequadas para consultas simples ou conversas curtas.

- Janelas de contexto médias (32 mil a 100 mil tokens)
Boas para processar documentos mais longos ou manter mais histórico de conversação.

- Janelas de contexto amplas (mais de 100 mil tokens)
    > Necessárias para analisar documentos inteiros, grandes bases de código, vídeos ou manter um histórico extenso de conversas.

Aplicação prática: Se você precisa processar documentos jurídicos extensos ou manter um histórico detalhado de conversas, modelos com janelas de contexto maiores como o Amazon Nova Premier (1M tokens) seriam mais apropriados. Isso permite a análise de conjuntos de dados maiores como grandes bases de código, múltiplos documentos e imagens, documentos com mais de 400 páginas ou vídeos de 90 minutos de duração.

# Acurácia
A precisão do modelo se refere à qualidade da execução da tarefa pretendida e ao fornecimento de informações corretas. O que considerar:

- Precisão factual
    > Qual é a importância do modelo fornecer informações factualmente corretas?

- Seguindo instruções
    > Alguns modelos são melhores em seguir instruções complexas com precisão.

- Tendência à alucinação
    > Todos os modelos podem "alucinar" ou gerar informações incorretas, mas alguns são mais propensos a isso do que outros.

- Data de corte do conhecimento
    > Os modelos têm diferentes datas de corte de treinamento, o que afeta seu conhecimento sobre eventos recentes.

Aplicação prática: Para aplicações onde a precisão é crítica (como conselhos médicos ou financeiros), escolha modelos com melhor fundamentação factual e menores taxas de alucinação. Considere implementar mecanismos adicionais de verificação para aplicações de alto risco.

## Características de Desempenho
O desempenho inclui aspectos como velocidade de resposta, throughput e confiabilidade. O que considerar:

- Latência
    > A velocidade de resposta a solicitações do modelo.

- Throughput
    > Quantas solicitações o modelo pode processar simultaneamente.

- Consistência
    > A confiabilidade das saídas do modelo em entradas semelhantes.

- Velocidade de geração de token
    > A velocidade na qual o modelo gera conteúdo.

Aplicação prática: Para aplicações voltadas ao cliente que exigem respostas rápidas, modelos como Claude 3 Haiku ou modelos Amazon Nova Lite podem ser preferíveis devido à menor latência. Para trabalhos de processamento em lote onde a velocidade é menos crítica, você pode priorizar outros fatores como acurácia ou custo.

## Eficiência de custos
Diferentes modelos têm preços variados. Consulte a página de preços do Amazon Bedrock para obter informações atualizadas sobre preços. Em geral, para modelos de geração de texto, você é cobrado por token de entrada processado e token de saída gerado. Para modelos de geração de imagens, você é cobrado por imagem gerada.

O que considerar:

- Custos de token de entrada
    > O que você paga pelo texto que envia ao modelo.

- Custos de tokens de saída
    > O que você paga pelo texto que o modelo gera.

- Custos totais de processamento
    > Para aplicações de alto volume, mesmo pequenas diferenças de custo por token podem acumular significativamente.

- Valor por capacidade
    > Às vezes, pagar mais por um modelo mais capaz resulta em melhor valor geral.

Aplicação prática: Para tarefas simples de alto volume, um modelo mais econômico como o Amazon Nova Lite pode ser apropriado. Para tarefas de raciocínio complexas nas quais a qualidade é primordial, o custo mais alto do Amazon Nova Premier pode ser justificado. Sempre calcule os custos estimados com base nos seus padrões de uso esperados.

## Recursos de IA Responsável
Os recursos de IA responsável ajudam a garantir que as saídas do modelo estejam alinhadas com diretrizes éticas e políticas organizacionais. O que considerar:

- Filtragem de conteúdo
    > Como o modelo lida com solicitações potencialmente prejudiciais ou inadequadas.

- Mitigação de viés
    > Capacidade do modelo de evitar ou reduziz várias formas de viés.

- Barreiras de proteção
    > Proteções incorporadas contra uso indevido ou geração de conteúdo prejudicial.

- Opções de personalização
    > Capacidade de ajustar as configurações de segurança para seu caso de uso específico.

Aplicação prática: Revise a documentação de cada modelo sobre recursos de segurança. Para aplicações voltadas ao público ou em domínios sensíveis, priorize modelos com fortes medidas de segurança e barreiras de proteção personalizáveis. O Amazon Bedrock também oferece recursos adicionais de barreiras de proteção que podem ser aplicados a qualquer modelo.

## Requisitos de caso de uso específico
Seu caso de uso específico pode ter requisitos exclusivos que influenciam a seleção do modelo.

O que considerar:

- Suporte a idiomas
    > Se você precisa de recursos multilíngues, verifique quais idiomas cada modelo suporta.

- Vocabulário especializado
    > Alguns modelos têm melhor desempenho com terminologia técnica, científica ou específica do setor.

- Conformidade regulatória
    > Determinados setores podem ter requisitos específicos em relação ao uso de modelos de IA.

- Necessidades de integração
    > Como o modelo se encaixará em seus sistemas e fluxos de trabalho existentes.

Aplicação prática: **Defina seus requisitos específicos antes de selecionar um modelo**. Por exemplo, se você precisa de forte suporte multilíngue para uma aplicação de atendimento ao cliente global, garanta que o modelo escolhido tenha bom desempenho em todos os idiomas necessários.

## Resumo
Selecionar o modelo de base correto no Amazon Bedrock envolve avaliar cuidadosamente múltiplos fatores, incluindo capacidades, modalidades, tamanho da janela de contexto, acurácia, desempenho, custo, recursos de IA responsável e os requisitos específicos do seu caso de uso. Ao avaliar sistematicamente esses critérios, você pode escolher o modelo que melhor se adapta às necessidades da sua aplicação, otimizando tanto o desempenho quanto a eficiência de custos.

Lembre-se de que a seleção de modelo é frequentemente um processo iterativo. À medida que você desenvolve sua aplicação, pode descobrir novos requisitos ou restrições que o levem a reconsiderar sua escolha de modelo. O Amazon Bedrock facilita a experimentação com diferentes modelos, permitindo que você refine sua seleção ao longo do tempo.

## Segurança e Conformidade

## Privacidade e Segurança do Modelo
## Controles de Privacidade e Barreiras de Proteção
Os controles de privacidade e barreiras de proteção fornecem mecanismos essenciais para proteger informações sensíveis e garantir o uso responsável da IA. 

As Barreiras de Proteção do Amazon Bedrock permitem que as organizações implementem políticas de filtragem de conteúdo alinhadas com seus valores e requisitos de conformidade. Essas barreiras de proteção podem ser aplicadas tanto aos prompts de entrada quanto às respostas geradas pelo modelo, ajudando a prevenir a transmissão ou geração de conteúdo prejudicial ou inadequado. 

As organizações podem personalizar essas barreiras de proteção para filtrar categorias específicas de conteúdo, como linguagem imprópria, informações pessoais ou sensibilidades específicas a determinados tópicos.

## Resumo
A estrutura de segurança do Amazon Bedrock integra controle de acesso abrangente, permitindo permissões granulares para acesso e operações de modelos. A segurança de rede da plataforma é construída em torno do AWS PrivateLink, fornecendo endpoints de VPC seguros para operações de runtime e gerenciamento, garantindo que todo o tráfego permaneça dentro da infraestrutura de rede privada da AWS sem exposição à internet pública. Os controles de privacidade incluem barreiras de proteção personalizáveis para filtragem de conteúdo, protegendo contra conteúdo inadequado e informações sensíveis. O sistema implementa recursos de gerenciamento de recursos por meio de tags para alocação de custos e controle de acesso.

Essa abordagem de segurança em várias camadas garante que as organizações possam inovar com tecnologias de IA enquanto mantêm rígidos padrões de segurança e conformidade, com todos os componentes trabalhando juntos para fornecer um ambiente de implantação de IA seguro, dimensionável e responsável.

## Playground

## Descrição
A equipe de negócios da AnyCompany deseja encontrar o melhor modelo de IA para sua experiência de IA de atendimento ao cliente baseada em chat, mas não possui um método de avaliação claro. Eles desejam comparar minuciosamente diferentes modelos que suportam texto e imagens durante as conversas com os clientes para fornecer interações ideais com os clientes.

## Conversa
Usando um cenário comum de atendimento ao cliente, podemos executar diferentes modelos para uma comparação lado a lado de suas respostas.
Joseph Trindade
Isso é perfeito para o nosso caso de uso. Você pode nos explicar como comparar as respostas?
Você
O console do Amazon Bedrock oferece vários Playgrounds onde podemos comparar respostas de diferentes modelos de IA. Podemos testar diversos prompts e ver como os diferentes modelos respondem, para avaliar e comparar o desempenho deles lado a lado com base em diferentes variáveis.

## Casos de uso para o Amazon Bedrock AgentCore

Existem muitos casos de uso diferentes para o AgentCore. Analise os seguintes para saber mais.

- Equipe agentes com ferramentas e capacidades integradas 
    > Equipe agentes para se integrarem perfeitamente com ferramentas e recursos internos e externos. Crie agentes que possam lembrar interações com os usuários do seu agente.

- Implante com segurança em escala
    > Implante e escale com segurança agentes de IA dinâmicos e ferramentas, independentemente do framework, protocolo ou escolha de modelo, sem gerenciar nenhum recurso subjacente, com gerenciamento de identidade e acesso de agente perfeito.

- Teste e monitore agentes 
    > Obtenha insights operacionais profundos com visibilidade em tempo real sobre o uso dos agentes e métricas operacionais, como uso de tokens, latência, duração da sessão e taxas de erro.

## Amazon Q Developer Getting Started



