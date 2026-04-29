import logging
import re

import boto3

from ..settings import settings

logger = logging.getLogger("agent.guardrail")

_CPF_RE    = re.compile(r'\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}\b')
_CARD_RE   = re.compile(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b')
_ACCOUNT_RE = re.compile(r'\b\d{5,12}[-–]\d{1,2}\b')

# Nome precedido de marcador explícito — evita falsos positivos em
# "Banco Central", nomes de cidades, instituições, etc.
_NOME_SEQ = (
    r'[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇ][a-záéíóúâêîôûãõàèìòùç]+'
    r'(?:\s+(?:(?:da|de|do|dos|das|e)\s+)?'
    r'[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇ][a-záéíóúâêîôûãõàèìòùç]+){1,5}'
)
_NOME_RE = re.compile(
    # marcadores em grupo capturável (group 1) com flag case-insensitive;
    # \b em "sou" evita casar dentro de palavras como "recusou"
    r'((?i:meu nome é\s+|nome\s*[eé:]?\s+|\bsou (?:o|a)\s+|'
    r'titular[:\s]+|portador[a]?\s+do\s+cpf\b[^,]*,\s*))'
    # sequência do nome (group 2): case-sensitive — exige inicial maiúscula
    + rf'({_NOME_SEQ})',
    re.UNICODE,
)

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
    "ignore previous instructions", "repita as instruções", "prompt inicial",
    "histórico de conversas", "dados dos outros clientes", "você é agora dan",
    "sem filtros", "sem restrições", "aja como o gerente",
]

_THREAT_TERMS = [
    "vou explodir", "vou incendiar", "vou machucar", "vou te encontrar",
    "sei onde vocês moram", "sei onde você mora", "vocês vão se arrepender",
    "vou matar", "vou destruir a agência",
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
    """Chama Bedrock apply_guardrail e devolve {"action", "outputs", "assessments"}.
    source=INPUT usa GUARDRAIL_ID; source=OUTPUT usa GUARDRAIL_ID_OUTPUT (fallback para GUARDRAIL_ID).
    """
    if source == "OUTPUT" and settings.GUARDRAIL_ID_OUTPUT:
        gid     = settings.GUARDRAIL_ID_OUTPUT
        gver    = settings.GUARDRAIL_VERSION_OUTPUT
    else:
        gid     = settings.GUARDRAIL_ID
        gver    = settings.GUARDRAIL_VERSION
    client = _bedrock_runtime()
    resp = client.apply_guardrail(
        guardrailIdentifier=gid,
        guardrailVersion=gver,
        source=source,
        content=[{"text": {"text": text}}],
    )
    return {
        "action":      resp.get("action", "NONE"),
        "outputs":     resp.get("outputs", []),
        "assessments": resp.get("assessments", []),
    }


def _extract_block_reason(assessments: list) -> str:
    parts = []
    for a in assessments:
        for t in a.get("topicPolicy", {}).get("topics", []):
            if t.get("action") == "BLOCKED":
                parts.append(t["name"])
        for f in a.get("contentPolicy", {}).get("filters", []):
            if f.get("action") == "BLOCKED":
                conf = f.get("confidence", "")
                parts.append(f"{f['type']} ({conf})" if conf else f["type"])
    return "; ".join(parts) if parts else "bedrock_guardrail"


# ── Input guardrail ────────────────────────────────────────────────────────────

def check_input(text: str) -> dict:
    """
    Valida o texto de entrada antes de entrar no pipeline.
    Retorna {"blocked": bool, "reason": str | None, "sanitized_text": str}.
    Não sanitiza PII — isso é responsabilidade do guardrail de saída.
    """
    if settings.GUARDRAIL_ID:
        try:
            r = _apply("INPUT", text)
            logger.info("guardrail INPUT action=%s", r["action"])
            if r["action"] == "GUARDRAIL_INTERVENED":
                reason = _extract_block_reason(r["assessments"])
                return {"blocked": True, "reason": "bedrock_guardrail", "block_reason": reason, "sanitized_text": text}
            return {"blocked": False, "reason": None, "sanitized_text": text}
        except Exception:
            logger.exception("erro Bedrock guardrail INPUT — fallback local")

    return _local_input_check(text)


def _local_input_check(text: str) -> dict:
    lower = text.lower()
    if any(term in lower for term in _INJECTION_TERMS):
        return {"blocked": True, "reason": "prompt_injection_local", "sanitized_text": text}
    if any(term in lower for term in _THREAT_TERMS):
        return {"blocked": True, "reason": "ameaca_direta_local", "sanitized_text": text}
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

    if settings.GUARDRAIL_ID_OUTPUT or settings.GUARDRAIL_ID:
        try:
            r = _apply("OUTPUT", text)
            if r["action"] == "GUARDRAIL_INTERVENED":
                # Quando o guardrail bloqueia (falso positivo de content policy),
                # outputs[0] contém blockedOutputsMessaging — não o texto sanitizado.
                # Nesse caso, mantemos o original e aplicamos apenas o regex local.
                logger.warning("guardrail OUTPUT bloqueou campo=%s — usando regex como fallback", field)
            else:
                outputs = r["outputs"]
                text = outputs[0].get("text", text) if outputs else text
        except Exception:
            logger.exception("erro Bedrock guardrail OUTPUT campo=%s — fallback regex", field)

    return _regex_sanitize(text)


def _regex_sanitize(text: str) -> str:
    text = _CPF_RE.sub("[CPF OMITIDO]", text)
    text = _CARD_RE.sub("[CARTÃO OMITIDO]", text)
    text = _ACCOUNT_RE.sub("[CONTA OMITIDA]", text)
    text = _NOME_RE.sub(r'\1[NOME OMITIDO]', text)
    return text
