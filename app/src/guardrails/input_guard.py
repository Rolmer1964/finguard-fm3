"""Guardrail de entrada usando Bedrock Guardrails (apply_guardrail).

Bloqueia, no início do grafo:
- Prompt injection / jailbreak / extração de system prompt
- Conteúdo fora do escopo de reclamação financeira
- Ameaças explícitas a pessoas / instituições
- (Opcional) PII de entrada

A configuração viva (denied topics, content filters, sensitive info) é feita
no console AWS — aqui só chamamos o guardrail pelo ID configurado em .env.

Se BEDROCK_GUARDRAIL_ID estiver vazio, este nó vira no-op (loga warning).
Útil para dev local antes de criar o guardrail.
"""

from __future__ import annotations

import json
import logging

import boto3

from ..settings import settings

logger = logging.getLogger("guardrail.input")

POLITE_BLOCK_MESSAGE = (
    "Não foi possível processar essa entrada. Por favor, descreva sua reclamação "
    "de forma clara e objetiva, sem instruções ao sistema, ameaças ou conteúdo "
    "que não se relacione a um problema com produto ou serviço financeiro."
)


def _client():
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        aws_session_token=settings.AWS_SESSION_TOKEN or None,
    )


def check_input(text: str) -> dict:
    """Aplica o guardrail Bedrock no texto. Retorna {'allowed': bool, 'reason': str|None, 'raw': dict}."""
    if not settings.BEDROCK_GUARDRAIL_ID:
        logger.warning("BEDROCK_GUARDRAIL_ID não configurado — input_guard em modo no-op")
        return {"allowed": True, "reason": None, "raw": {"action": "NONE", "skipped": True}}

    try:
        resp = _client().apply_guardrail(
            guardrailIdentifier=settings.BEDROCK_GUARDRAIL_ID,
            guardrailVersion=settings.BEDROCK_GUARDRAIL_VERSION,
            source="INPUT",
            content=[{"text": {"text": text}}],
        )
    except Exception as exc:
        logger.exception("falha aplicando input guardrail: %s", exc)
        return {"allowed": True, "reason": None, "raw": {"action": "ERROR", "error": str(exc)}}

    action = resp.get("action", "NONE")
    if action == "GUARDRAIL_INTERVENED":
        outputs = resp.get("outputs") or []
        reason = outputs[0].get("text") if outputs else None
        return {"allowed": False, "reason": reason or POLITE_BLOCK_MESSAGE, "raw": resp}
    return {"allowed": True, "reason": None, "raw": resp}
