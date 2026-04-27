import logging
import re

import boto3

from ..settings import settings

logger = logging.getLogger("agent.guardrail")

_CPF_RE    = re.compile(r'\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}\b')
_CARD_RE   = re.compile(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b')
_ACCOUNT_RE = re.compile(r'\b\d{5,12}[-–]\d{1,2}\b')

BLOCKED_INPUT_MESSAGE = (
    "Esta entrada não pode ser processada pelo FinGuard. "
    "O sistema está disponível exclusivamente para análise de reclamações bancárias de clientes. "
    "Por favor, envie o texto de uma reclamação válida."
)

_INJECTION_TERMS = [
    "ignore suas instruções", "ignore as instruções anteriores",
    "ignore as instruções", "esqueça tudo que foi dito",
    "you are now", "você agora é", "finja ser", "aja como se fosse",
    "pretend to be", "jailbreak", "system prompt", "prompt injection",
    "revelar suas instruções", "mostre seu prompt", "what is your system prompt",
    "ignore previous instructions",
]


def _bedrock_runtime():
    kwargs: dict = {"region_name": settings.AWS_REGION}
    if settings.AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"]     = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        if settings.AWS_SESSION_TOKEN:
            kwargs["aws_session_token"] = settings.AWS_SESSION_TOKEN
    return boto3.client("bedrock-runtime", **kwargs)


def _apply(source: str, text: str) -> dict:
    """Chama Bedrock apply_guardrail e devolve {"action", "outputs"}."""
    client = _bedrock_runtime()
    resp = client.apply_guardrail(
        guardrailIdentifier=settings.GUARDRAIL_ID,
        guardrailVersion=settings.GUARDRAIL_VERSION,
        source=source,
        content=[{"text": {"text": text}}],
    )
    return {
        "action": resp.get("action", "NONE"),
        "outputs": resp.get("outputs", []),
    }


# ── Input guardrail ────────────────────────────────────────────────────────────

def check_input(text: str) -> dict:
    """
    Valida o texto de entrada antes de entrar no pipeline.
    Retorna {"blocked": bool, "reason": str | None, "sanitized_text": str}.
    """
    if settings.GUARDRAIL_ID:
        try:
            r = _apply("INPUT", text)
            logger.info("guardrail INPUT action=%s", r["action"])
            if r["action"] == "GUARDRAIL_INTERVENED":
                return {"blocked": True, "reason": "bedrock_guardrail", "sanitized_text": text}
            outputs = r["outputs"]
            sanitized = outputs[0].get("text", text) if outputs else text
            return {"blocked": False, "reason": None, "sanitized_text": sanitized}
        except Exception:
            logger.exception("erro Bedrock guardrail INPUT — fallback local")

    return _local_input_check(text)


def _local_input_check(text: str) -> dict:
    lower = text.lower()
    if any(term in lower for term in _INJECTION_TERMS):
        return {"blocked": True, "reason": "prompt_injection_local", "sanitized_text": text}
    if len(text.strip()) < 10:
        return {"blocked": True, "reason": "input_muito_curto", "sanitized_text": text}
    return {"blocked": False, "reason": None, "sanitized_text": text}


# ── Output guardrail ───────────────────────────────────────────────────────────

def sanitize_output(text: str, field: str = "") -> str:
    """
    Sanitiza o texto de saída removendo/anonimizando dados sensíveis.
    Usa Bedrock guardrail (quando configurado) + regex como defesa em profundidade.
    """
    if not text:
        return text

    if settings.GUARDRAIL_ID:
        try:
            r = _apply("OUTPUT", text)
            outputs = r["outputs"]
            sanitized = outputs[0].get("text", text) if outputs else text
            if r["action"] == "GUARDRAIL_INTERVENED":
                logger.warning("guardrail OUTPUT interveio campo=%s", field)
            text = sanitized
        except Exception:
            logger.exception("erro Bedrock guardrail OUTPUT campo=%s — fallback regex", field)

    return _regex_sanitize(text)


def _regex_sanitize(text: str) -> str:
    text = _CPF_RE.sub("[CPF OMITIDO]", text)
    text = _CARD_RE.sub("[CARTÃO OMITIDO]", text)
    text = _ACCOUNT_RE.sub("[CONTA OMITIDA]", text)
    return text
