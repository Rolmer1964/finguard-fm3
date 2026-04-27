import json
import logging
import re

import boto3

from .settings import settings

logger = logging.getLogger("orchestrator.llm")


def _bedrock_runtime():
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        aws_session_token=settings.AWS_SESSION_TOKEN or None,
    )


def _bedrock_control():
    # 'bedrock-runtime' inclui apply_guardrail (não precisa de cliente separado para chamar guardrails).
    return _bedrock_runtime()


def invoke_claude(model_id: str, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.2) -> str:
    """Invoca um modelo Claude via Bedrock com a Messages API. Retorna o texto da resposta."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    client = _bedrock_runtime()
    resp = client.invoke_model(
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
        body=json.dumps(body),
    )
    payload = json.loads(resp["body"].read())
    parts = payload.get("content", [])
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    return text.strip()


def parse_json_object(text: str) -> dict:
    """Extrai o primeiro objeto JSON de uma resposta de LLM (tolerante a markdown fence)."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
    return json.loads(cleaned)


def apply_guardrail(text: str, *, source: str = "INPUT") -> dict:
    """Aplica um Bedrock Guardrail. Retorna dict com 'action' (NONE/GUARDRAIL_INTERVENED).

    Se BEDROCK_GUARDRAIL_ID não estiver configurado, retorna NONE (no-op) e loga warning.
    """
    if not settings.BEDROCK_GUARDRAIL_ID:
        logger.warning("BEDROCK_GUARDRAIL_ID não configurado; pulando guardrail (%s).", source)
        return {"action": "NONE", "outputs": [{"text": text}]}
    client = _bedrock_control()
    resp = client.apply_guardrail(
        guardrailIdentifier=settings.BEDROCK_GUARDRAIL_ID,
        guardrailVersion=settings.BEDROCK_GUARDRAIL_VERSION,
        source=source,
        content=[{"text": {"text": text}}],
    )
    return resp
