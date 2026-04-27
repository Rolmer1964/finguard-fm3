"""Guardrail de saída: garante que dados sensíveis (PII) não vazem nos textos
livres do payload final (resumo e justificativa de risco).

Estratégia em duas camadas:
1. Regex local (rápido, determinístico): CPF, conta, cartão de crédito.
2. (Opcional) Bedrock Guardrail no source=OUTPUT — se BEDROCK_GUARDRAIL_ID
   estiver configurado e tiver Sensitive Information Filters habilitados, é
   chamado para uma checagem adicional. Não bloqueia o pipeline em falha;
   apenas registra warnings.

A regex local é a defesa primária e suficiente para a entrega. O Bedrock
Guardrail é defesa em profundidade.
"""

from __future__ import annotations

import json
import logging
import re

import boto3

from ..settings import settings

logger = logging.getLogger("guardrail.output")

# CPF: 999.999.999-99 ou 99999999999
CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
# Conta corrente: 99999-9 ou 999999-9
CONTA_RE = re.compile(r"\b\d{4,6}-?\d\b")
# Cartão: 4 grupos de 4 dígitos (com ou sem espaço/hífen)
CARTAO_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")


def _redact_local(text: str | None) -> tuple[str | None, list[str]]:
    """Aplica regex de PII e retorna (texto_limpo, lista_de_tipos_redactados)."""
    if not text:
        return text, []
    found: list[str] = []
    out = text
    if CARTAO_RE.search(out):
        out = CARTAO_RE.sub("[CARTÃO REDACTADO]", out)
        found.append("cartao")
    if CPF_RE.search(out):
        out = CPF_RE.sub("[CPF REDACTADO]", out)
        found.append("cpf")
    if CONTA_RE.search(out):
        out = CONTA_RE.sub("[CONTA REDACTADA]", out)
        found.append("conta")
    return out, found


def _bedrock_check(text: str) -> dict:
    """Aplica o guardrail Bedrock em modo OUTPUT. Falha-aberto: erros não bloqueiam."""
    if not settings.BEDROCK_GUARDRAIL_ID:
        return {"action": "NONE", "skipped": True}
    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            aws_session_token=settings.AWS_SESSION_TOKEN or None,
        )
        resp = client.apply_guardrail(
            guardrailIdentifier=settings.BEDROCK_GUARDRAIL_ID,
            guardrailVersion=settings.BEDROCK_GUARDRAIL_VERSION,
            source="OUTPUT",
            content=[{"text": {"text": text}}],
        )
        return resp
    except Exception as exc:
        logger.warning("output guardrail Bedrock falhou (não bloqueia): %s", exc)
        return {"action": "ERROR", "error": str(exc)}


def sanitize_payload(payload: dict) -> dict:
    """Aplica redaction de PII em campos textuais do payload final.

    Não bloqueia: redacta. O payload sai sempre — possíveis PII são substituídas
    por marcadores explícitos antes de qualquer persistência ou exibição.
    """
    out = dict(payload)
    redacted_summary, found_s = _redact_local(out.get("summary"))
    redacted_just, found_r = _redact_local(out.get("risk_justification"))
    out["summary"] = redacted_summary
    out["risk_justification"] = redacted_just
    pii_found = sorted(set(found_s + found_r))
    if pii_found:
        logger.warning("output_guard redactou PII: %s", pii_found)
    out["_pii_redacted"] = pii_found

    # Camada 2 — checagem Bedrock (defesa em profundidade, não-bloqueante)
    if settings.BEDROCK_GUARDRAIL_ID:
        joined = (out.get("summary") or "") + "\n" + (out.get("risk_justification") or "")
        bedrock_resp = _bedrock_check(joined)
        out["_bedrock_output_action"] = bedrock_resp.get("action", "NONE")

    return out
