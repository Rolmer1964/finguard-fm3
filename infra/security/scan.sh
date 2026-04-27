#!/usr/bin/env bash
# FinGuard - Verificação de segurança consolidada.
# Roda Bandit, Semgrep, pip-audit, npm audit e Trivy via containers efêmeros.
# Saída: infra/security/raw/<scan>.txt + infra/security/report-YYYYMMDD-HHMMSS.md

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RAW_DIR="${ROOT}/infra/security/raw"
TS="$(date +%Y%m%d-%H%M%S)"
REPORT="${ROOT}/infra/security/report-${TS}.md"

mkdir -p "$RAW_DIR"

step() { echo ""; echo "==> $1"; }

cnt() {
  # Conta ocorrências de uma string (case-insensitive) num arquivo. Retorna 0 se arquivo ausente.
  local f="$1" pat="$2"
  [[ -f "$f" ]] || { echo 0; return; }
  grep -ic "$pat" "$f" 2>/dev/null || echo 0
}

# ---------- Bandit (Python SAST) ----------
step "Bandit (Python SAST)"
docker run --rm -v "${ROOT}:/src" -w /src python:3.12-slim bash -c \
  "pip install -q bandit && bandit -r services/*/app -f txt" \
  > "${RAW_DIR}/bandit.txt" 2>&1 || true

# ---------- Semgrep ----------
step "Semgrep (regras Python + OWASP + JWT)"
docker run --rm -v "${ROOT}:/src" returntocorp/semgrep \
  semgrep --config p/python --config p/owasp-top-ten --config p/jwt --error --quiet /src/services /src/scripts \
  > "${RAW_DIR}/semgrep.txt" 2>&1 || true

# ---------- pip-audit por serviço ----------
step "pip-audit (vulns nas dependências Python)"
: > "${RAW_DIR}/pip-audit.txt"
for svc in services/*/; do
  name="$(basename "$svc")"
  echo "--- ${name} ---" >> "${RAW_DIR}/pip-audit.txt"
  docker run --rm -v "${ROOT}/${svc}:/src" -w /src python:3.12-slim bash -c \
    "pip install -q pip-audit && pip-audit -r requirements.txt --strict" \
    >> "${RAW_DIR}/pip-audit.txt" 2>&1 || true
done

# ---------- npm audit no frontend ----------
step "npm audit (frontend)"
docker run --rm -v "${ROOT}/frontend:/src" -w /src node:20-alpine sh -c \
  "npm install --omit=dev --silent --no-audit --no-fund 2>/dev/null && npm audit --omit=dev --json" \
  > "${RAW_DIR}/npm-audit.json" 2>&1 || true

# ---------- Trivy nas imagens construídas ----------
step "Trivy (imagens Docker)"
: > "${RAW_DIR}/trivy.txt"
docker compose --project-directory "$ROOT" config --images 2>/dev/null | sort -u | while read -r img; do
  [[ -z "$img" ]] && continue
  echo "--- ${img} ---" >> "${RAW_DIR}/trivy.txt"
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest \
    image --severity HIGH,CRITICAL --no-progress --quiet "$img" \
    >> "${RAW_DIR}/trivy.txt" 2>&1 || true
done

# ---------- Relatório consolidado ----------
step "Consolidando relatório em ${REPORT}"
{
  echo "# FinGuard - Relatório de segurança"
  echo ""
  echo "Gerado em: $(date '+%Y-%m-%d %H:%M:%S')"
  echo ""
  echo "## Resumo por ferramenta"
  echo ""
  echo "| Ferramenta | High/Critical | Issues totais (aprox.) |"
  echo "|---|---|---|"
  echo "| Bandit     | $(cnt "${RAW_DIR}/bandit.txt" 'severity: high') | $(cnt "${RAW_DIR}/bandit.txt" 'issue:') |"
  echo "| Semgrep    | $(cnt "${RAW_DIR}/semgrep.txt" 'error') | $(cnt "${RAW_DIR}/semgrep.txt" 'rule id:') |"
  echo "| pip-audit  | - | $(cnt "${RAW_DIR}/pip-audit.txt" 'vulnerability') |"
  echo "| npm audit  | $(cnt "${RAW_DIR}/npm-audit.json" '\"severity\":\"high\"\|\"severity\":\"critical\"') | $(cnt "${RAW_DIR}/npm-audit.json" '\"vulnerabilities\"') |"
  echo "| Trivy      | $(cnt "${RAW_DIR}/trivy.txt" 'high\|critical') | $(cnt "${RAW_DIR}/trivy.txt" 'cve-') |"
  echo ""
  echo "Saída bruta de cada ferramenta em \`infra/security/raw/\`."
  echo ""
  echo "## Próximos passos"
  echo "- Investigar findings High/Critical antes de qualquer release."
  echo "- Atualizar dependências apontadas por pip-audit/npm audit."
  echo "- Aplicar mitigações para findings de Bandit/Semgrep marcados como confirmados."
} > "$REPORT"

echo ""
echo "OK. Relatório: $REPORT"
echo "Saídas brutas:  $RAW_DIR"
