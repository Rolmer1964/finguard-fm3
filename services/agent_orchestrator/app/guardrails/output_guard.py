import logging
import re

logger = logging.getLogger("orchestrator.output_guard")

# CPF: 999.999.999-99 ou 99999999999
CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
# Conta corrente: padrões 99999-9 ou ag/conta 9999/99999-9
CONTA_RE = re.compile(r"\b\d{4,6}-?\d\b")
# Cartão de crédito: 4 grupos de 4 dígitos (com/sem espaço/hífen)
CARTAO_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")


def _redact(text: str | None) -> str | None:
    if not text:
        return text
    out = CARTAO_RE.sub("[CARTÃO REDACTADO]", text)
    out = CPF_RE.sub("[CPF REDACTADO]", out)
    out = CONTA_RE.sub("[CONTA REDACTADA]", out)
    return out


def sanitize_payload(payload: dict) -> dict:
    """Aplica redaction de PII em campos textuais do payload final.

    Não bloqueia: redacta. Mantém o tom profissional preservado pelos prompts dos agentes.
    """
    out = dict(payload)
    out["summary"] = _redact(out.get("summary"))
    out["risk_justification"] = _redact(out.get("risk_justification"))
    return out
