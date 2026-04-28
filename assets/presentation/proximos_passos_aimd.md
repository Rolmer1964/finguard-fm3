# FinGuard — Análise Completa do Pipeline e Roadmap AIMD

Documento de apoio para a equipe. Consolida todas as execuções realizadas durante o desenvolvimento
do Nível 3, registra as fontes de dados, os padrões identificados e as implicações para produção.

---

## 1. Fontes de dados — todos os relatórios

| Relatório | Label | Registros | Contexto |
|---|---|---|---|
| `report_2026-04-27-22-54-58` | 500-throttle | 500 | Primeira execução em escala. Sem multi-pass. Sem log disponível. |
| `report_2026-04-27-23-32-49` | Inter-1 | 100 | Primeiro batch de 100 reg. Sem multi-pass. 19 falhas definitivas. |
| `report_2026-04-27-23-48-37` | Inter-2 | 100 | Multi-pass implementado (retry fixo, `RETRY_WORKERS=2`). 0 falhas. |
| `report_2026-04-28-05-56-46` | Baseline-10 | 10 | Teste de calibração. 23s de duração. Sem throttling. Referência de latência mínima. |
| `report_2026-04-28-06-19-29` | Batch 0 | 100 | AIMD implementado com limiar frouxo (>20%). Sem ajuste efetivo. |
| `report_2026-04-28-06-40-31` | Batch 1 | 100 | AIMD com limiar corrigido (>5%). Convergiu em 2 passes: 5→2 workers. |
| `report_2026-04-28-06-55-57` | Batch 2 | 100 | Parâmetros convergidos (2 workers, 1.0s delay). Passe único, 0% throttle. |

Arquivos de log disponíveis (container stdout):

| Arquivo | Horário início (BRT) | Batch correspondente |
|---|---|---|
| `batch_500_20260427_202547.log` | 23:25 | Inter-1 (23:32) — 100 reg, workers=5, 19 falhas definitivas |
| `batch_500_20260427_204813.log` | 23:48 | Inter-2 (23:48) — 100 reg, pass1 workers=5 → pass2 workers=2 |
| `batch_500_20260428_033905.log` | 03:39 UTC = 00:39 BRT | Batch 1 (06:40) — AIMD convergência |
| `batch_500_20260428_035541.log` | 03:55 UTC = 00:55 BRT | Batch 2 (06:55) — passe único |

> Nota: os logs de 500-throttle e Baseline-10 não têm arquivo de log correspondente
> (sessões de container anteriores ou não capturadas).

---

## 2. Linha do tempo da evolução do sistema

```
22:54  500-throttle ─── sem multi-pass, sem retry ──────────────── 108/500 bloqueados, muitas falhas
23:32  Inter-1      ─── sem multi-pass, 19 falhas definitivas ──── descoberta: retry é necessário
23:48  Inter-2      ─── multi-pass com RETRY_WORKERS=2 (fixo) ──── 0 falhas, mas sem adaptação
05:56  Baseline-10  ─── 10 registros, calibração ────────────────── latência mínima registrada
06:19  Batch 0      ─── AIMD implementado, limiar 20% (bug) ─────── workers=5 em todos os passes
06:40  Batch 1      ─── AIMD corrigido, limiar 5% ───────────────── convergência real: 5→2 workers
06:55  Batch 2      ─── parâmetros convergidos aplicados ─────────── passe único, 0% throttle
```

A evolução tem 4 fases distintas:
1. **Sem controle**: falhas definitivas, sem recuperação (22:54, 23:32)
2. **Multi-pass fixo**: recuperação garantida, mas sem adaptação de parâmetros (23:48)
3. **AIMD com bug**: mecanismo presente mas ineficaz por limiar frouxo (06:19)
4. **AIMD funcional**: convergência real e sustentada (06:40, 06:55)

---

## 3. Métricas consolidadas de todos os relatórios

### 3.1 Tabela geral

| Relatório | Total | Bloq. | Bloq.% | E2E avg | E2E P95 | E2E CV | Haiku avg | Haiku P95 | Haiku CV | Sonnet avg | Sonnet P95 | Sonnet CV |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 500-throttle | 500 | 108 | 21.6% | 11.959ms | 19.603ms | 27.9% | 5.022ms | 12.608ms | 64.7% | 5.097ms | 6.038ms | **17.0%** |
| Inter-1 | 100 | 1 | 1.0% | 10.762ms | 19.047ms | 29.7% | 4.097ms | 10.311ms | 71.9% | 4.767ms | 7.392ms | 28.2% |
| Inter-2 | 100 | 1 | 1.0% | 10.605ms | 17.816ms | 30.9% | 4.246ms | 11.719ms | 75.0% | 4.457ms | 5.570ms | **13.3%** |
| Baseline-10 | 10 | 0 | 0.0% | 10.718ms | 13.683ms | **14.8%** | **2.201ms** | 2.458ms | **8.2%** | 6.233ms | 8.906ms | 22.3% |
| Batch 0 | 100 | 26 | 26.0% | 11.476ms | 18.405ms | 24.0% | 3.986ms | 11.041ms | 65.0% | 5.600ms | 8.177ms | 18.1% |
| Batch 1 | 100 | 15 | 15.0% | 11.982ms | 22.054ms | 32.3% | 4.500ms | 12.012ms | 74.9% | 5.634ms | 7.313ms | 21.0% |
| **Batch 2** | 100 | 17 | 17.0% | **10.114ms** | **11.811ms** | **11.9%** | 2.258ms | 3.191ms | 22.6% | 6.036ms | 7.775ms | 18.2% |

### 3.2 O que o CV revela ao longo do tempo

O Coeficiente de Variação (CV) do E2E é o melhor indicador de qualidade do pipeline —
mede a previsibilidade, não apenas a velocidade:

```
500-throttle │ ████████████████████████████ 27.9%
Inter-1      │ █████████████████████████████ 29.7%
Inter-2      │ ██████████████████████████████ 30.9%
Batch 0      │ ████████████████████████ 24.0%
Batch 1      │ ████████████████████████████████ 32.3%
Baseline-10  │ ██████████████ 14.8%  (amostra n=10)
Batch 2      │ ████████████ 11.9%  ← mais estável
```

O Batch 2 atingiu CV 11.9% — menos da metade da variância de qualquer batch com throttling.
Em produção, isso significa SLAs mais previsíveis e menos surpresas nos percentis altos.

---

## 4. O Haiku como monitor de throttling

### 4.1 Latência natural do Haiku

O Baseline-10 (10 registros sequenciais, sem pressão concorrente) estabelece a referência:

```
Haiku natural: avg ≈ 2.201ms | P95 = 2.458ms | CV = 8.2%
```

O Batch 2 (100 registros, 2 workers, 0% throttle) confirma:

```
Haiku sem throttle: avg ≈ 2.258ms | P95 = 3.191ms | CV = 22.6%
```

O CV sobe de 8.2% para 22.6% com paralelismo, mas a média permanece estável (~2.2s).

### 4.2 Haiku sob throttling

Todos os batches com throttling mostram Haiku inflado pelo backoff exponencial:

| Relatório | Haiku avg | Fator vs natural | Haiku CV |
|---|---|---|---|
| Baseline-10 (referência) | 2.201ms | 1.0× | 8.2% |
| Batch 2 (0% throttle) | 2.258ms | 1.0× | 22.6% |
| Batch 0 (13% throttle) | 3.986ms | 1.8× | 65.0% |
| Inter-1 (throttle, sem retry) | 4.097ms | 1.9× | 71.9% |
| Inter-2 (throttle, retry fixo) | 4.246ms | 1.9× | 75.0% |
| Batch 1 (17% throttle, pass1) | 4.500ms | 2.0× | 74.9% |
| 500-throttle | 5.022ms | 2.3× | 64.7% |

**Regra prática**: se `Haiku avg > 3.0s`, o sistema está sob pressão de throttling.
Se `Haiku CV > 50%`, retries estão ocorrendo de forma expressiva.

O Haiku funciona como um **canário do pipeline**: sua variância sobe antes que o throttling
se torne visível nos percentis do E2E total.

---

## 5. O paradoxo do Sonnet

### 5.1 Os dados

Em todos os batches com throttling, o Sonnet aparece mais rápido em média do que no Batch 2 limpo:

| Relatório | Sonnet avg | Sonnet P95 | Sonnet CV | Condição |
|---|---|---|---|---|
| Baseline-10 | **6.233ms** | 8.906ms | 22.3% | Sem pressão, n=10 |
| Batch 2 | **6.036ms** | 7.775ms | 18.2% | 0% throttle, 2w limpos |
| Batch 0 | 5.600ms | 8.177ms | 18.1% | 13% throttle |
| Inter-1 | 4.767ms | 7.392ms | 28.2% | throttle, sem retry |
| Inter-2 | 4.457ms | 5.570ms | 13.3% | throttle, retry fixo |
| Batch 1 | 5.634ms | 7.313ms | 21.0% | 17% throttle, AIMD |
| 500-throttle | 5.097ms | 6.038ms | **17.0%** | throttle pesado |

O Baseline-10 e o Batch 2 — os dois cenários sem throttling — têm Sonnet avg 6.0–6.2s,
enquanto os batches throttled ficam entre 4.4–5.6s.

### 5.2 A explicação: cascata de rate limiting

O pipeline de cada registro é sequencial:

```
[Guardrail Input] → [Haiku: Triagem] → [Sonnet: Risco + RAG] → [Guardrail Output]
```

Com throttling no Haiku, os workers ficam presos em backoff exponencial **antes** de chegarem
ao Sonnet. A pressão concorrente sobre o Sonnet cai naturalmente — ele recebe menos chamadas
simultâneas do que aparenta pelos números de workers.

Com 2 workers limpos (Batch 2), o fluxo é contínuo: ambos chegam ao Sonnet de forma regular
e sustentada. O Sonnet recebe carga mais alta e consistente do que no cenário throttled.

O Baseline-10 confirma: com apenas 10 registros praticamente sequenciais, o Sonnet mostra
seu tempo natural de ~6.2s — o mesmo que o Batch 2.

### 5.3 A métrica que desfaz a ilusão

Apesar do Sonnet ser "mais rápido" em média com throttling, os percentis altos revelam o custo real:

| Métrica | Batch 2 limpo | 500-throttle |
|---|---|---|
| Sonnet avg | 6.036ms | 5.097ms (-16%) |
| E2E P95 | **11.811ms** | 19.603ms (+66%) |
| E2E P99 | **15.441ms** | 21.758ms (+41%) |
| E2E CV | **11.9%** | 27.9% |

A "vantagem" do Sonnet no cenário throttled desaparece completamente quando se olha para P95 e P99.
O pipeline como um todo é 66% mais lento no P95 sob throttling.

### 5.4 Implicação: Sonnet como próximo gargalo

Com 2 workers fluindo de forma sustentada, o Sonnet recebe mais carga do que em qualquer
cenário throttled. Isso sugere que ao aumentarmos workers (3, 4...), o Sonnet pode atingir
seu próprio ponto de saturação antes do Haiku.

**Sinal a monitorar em produção**: se ao escalar workers o Sonnet P95 crescer
desproporcionalmente enquanto o Haiku permanece estável, o Sonnet se tornou o novo gargalo.
O AIMD atual não distingue qual modelo está causando o throttling — ele reage ao sintoma
(`ThrottlingException`) sem conhecer a origem.

---

## 6. A taxa de bloqueio pelo guardrail

A taxa de registros bloqueados varia significativamente entre os experimentos:

| Relatório | Bloqueados | Total | Taxa |
|---|---|---|---|
| Inter-1 | 1 | 100 | **1.0%** |
| Inter-2 | 1 | 100 | **1.0%** |
| Baseline-10 | 0 | 10 | 0.0% |
| Batch 1 | 15 | 100 | 15.0% |
| Batch 2 | 17 | 100 | 17.0% |
| Batch 0 | 26 | 100 | 26.0% |
| 500-throttle | 108 | 500 | 21.6% |

Cada batch usou um CSV diferente. A variação (0% a 26%) reflete a composição do dataset,
não variação no guardrail. **Dentro de um mesmo CSV, o guardrail é determinístico**: os
mesmos registros são sempre bloqueados, em qualquer ordem de processamento.

Implicação para dimensionamento: em um dataset real de reclamações bancárias, a taxa de
bloqueio depende do perfil do lote (agressividade do conteúdo, presença de dados pessoais
sensíveis, linguagem ofensiva). O guardrail de entrada deve ser considerado ao estimar a
capacidade efetiva de processamento — a taxa pode variar de 1% a 26%+ dependendo da origem
dos dados.

---

## 7. Por que não testamos 3 workers

### 7.1 O problema de escala no free tier

Com 2 workers a taxa efetiva de chamadas Bedrock é aproximadamente:

```
2 workers × 2 chamadas/registro ÷ (10s pipeline + 1s delay) ≈ 0.36 req/s ≈ 21 RPM
```

Ir para 3 workers aumenta essa pressão em **+50%**. No free tier, onde a margem entre
"estável" e "throttling" é estreita, cada worker adicional representa uma variação enorme.
O comportamento é quase binário: ou funciona, ou throttle.

### 7.2 Os dois cenários possíveis

| Cenário | O que descobrimos | Valor |
|---|---|---|
| Throttle → AIMD corrige de volta para 2 | Confirma o que já sabemos | Baixo |
| Sem throttle → 3 workers é estável | Ganho real de +50% de vazão | Alto |

Dado o tempo disponível e a narrativa já completa com 3 batches, não valeu a pena o risco.

### 7.3 Por que em produção esse problema não existe

Em free tier com 2–3 workers seguros, cada +1 worker representa +33% a +50% de variação.
Em produção com `provisioned throughput` e 10–20 workers disponíveis, o AIMD explora o espaço
em incrementos de **+5% a +10% por passe** — muito mais suave e controlado.

A cada batch bem-sucedido (`throttled == 0`), o Additive Increase atua gradualmente:

```python
workers = min(MAX_WORKERS, workers + 1)   # +1 worker a cada pass limpo
delay   = max(0.0, delay - 0.5)           # -0.5s de delay a cada pass limpo
```

Em uma conta com quota de 50+ RPM por modelo, o sistema partiria de 2 workers e
**descobriria automaticamente o ponto ótimo** ao longo das execuções — sem intervenção humana.

---

## 8. Resumo executivo para a equipe

### O que o AIMD resolve

- Descoberta automática do ponto de equilíbrio de workers e delay
- Recuperação de throttling via multi-pass sem intervenção humana
- Adaptação a mudanças de quota (corte de limite, horário de pico) sem reconfiguração
- Métricas por passe que tornam o comportamento do sistema observável e auditável

### O que o AIMD ainda não resolve

| Limitação | Detalhe |
|---|---|
| Distinção de modelo | Não sabe se o throttling vem do Haiku ou do Sonnet |
| TPM vs RPM | Reage ao sintoma (`ThrottlingException`), não à causa (tokens vs requests) |
| Aprendizado cross-session | Não persiste os parâmetros convergidos entre reinicializações (hoje feito via `.env`) |
| Ajuste diferenciado por modelo | Um único delay para todo o pipeline; modelos com limites diferentes não são tratados separadamente |

### Parâmetros descobertos empiricamente (free tier)

| Parâmetro | Valor | Motivo |
|---|---|---|
| `BATCH_MAX_WORKERS` | 2 | Limite prático do free tier (~5 RPM/modelo) |
| `BATCH_RATE_LIMIT_DELAY` | 1.0s | Espaçamento mínimo para zero throttling |
| `BATCH_MAX_RETRIES` | 2 | Tentativas por worker antes de escalar para multi-pass |
| `BATCH_MAX_PASSES` | 3 | Limite de passes de recuperação |
| `BATCH_RETRY_DELAY` | 15.0s | Espera base entre passes (multiplicada pelo throttle_rate) |

### Argumento de encerramento

> "O ponto de equilíbrio encontrado (2 workers, 1.0s delay) é específico para o free tier
> com ~5 RPM por modelo. Em produção, o AIMD reconvergeria automaticamente para um regime
> mais agressivo — mais workers, menos delay — sem nenhuma intervenção humana.
> O algoritmo não precisa saber a quota: ele a descobre.
> E se o Sonnet virar o novo gargalo ao escalar, o sistema detecta e recua — da mesma forma."
