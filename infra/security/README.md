# Verificação de segurança

`make security-scan` (ou `bash infra/security/scan.sh`) executa os scanners abaixo dentro de containers efêmeros, sem precisar instalar nada localmente.

| Ferramenta | O que verifica |
|---|---|
| **Bandit**    | Padrões inseguros em código Python (eval, hashlib fraco, secrets, etc.) |
| **Semgrep**   | Regras `p/python`, `p/owasp-top-ten`, `p/jwt` |
| **pip-audit** | Vulnerabilidades conhecidas nas dependências de cada serviço Python |
| **npm audit** | Vulnerabilidades nas dependências do frontend |
| **Trivy**     | CVEs (HIGH/CRITICAL) nas imagens Docker construídas |

## Saídas

- `infra/security/raw/<scanner>.txt|json` — saída crua de cada scanner.
- `infra/security/report-YYYYMMDD-HHMMSS.md` — relatório consolidado por severidade.

## Pré-requisitos

- Docker em execução (não precisa de Python/Node locais).
- Para o Trivy escanear imagens dos serviços, rode `make build` antes (precisa das imagens construídas).

## Tratamento dos achados

- **High/Critical**: investigar e corrigir antes de release. Se for falso positivo, documentar no PR.
- **Medium/Low**: priorizar conforme contexto e backlog.
- Falsos positivos comuns no Bandit (ex.: `B104 hardcoded_bind_all_interfaces` no `0.0.0.0` do uvicorn dentro de container) podem ser mitigados com `# nosec` quando o contexto for seguro.
