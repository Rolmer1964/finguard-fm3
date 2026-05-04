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

_PII_TYPE_LABELS: dict[str, str] = {
    "EMAIL":                   "E-mail",
    "EMAIL_ADDRESS":           "E-mail",
    "PHONE":                   "Telefone",
    "PHONE_NUMBER":            "Telefone",
    "NAME":                    "Nome",
    "CREDIT_DEBIT_NUMBER":     "Cartão",
    "CREDIT_DEBIT_EXPIRY":     "Validade cartão",
    "CREDIT_DEBIT_CVV":        "CVV",
    "AWS_ACCESS_KEY":          "Chave AWS",
    "AWS_SECRET_KEY":          "Chave secreta AWS",
    "IP_ADDRESS":              "IP",
    "ADDRESS":                 "Endereço",
    "US_SOCIAL_SECURITY_NUMBER": "CPF/SSN",
    "DRIVER_ID":               "CNH",
    "PASSPORT_NUMBER":         "Passaporte",
}

_CONTENT_LABELS: dict[str, str] = {
    "INSULTS":    "Linguagem ofensiva",
    "HATE":       "Discurso de ódio",
    "VIOLENCE":   "Violência",
    "SEXUAL":     "Conteúdo sexual",
    "MISCONDUCT": "Conduta imprópria",
    "PROMPT_ATTACK": "Prompt injection",
}


def _extract_output_detail(assessments: list) -> dict:
    pii_types: list[str] = []
    content: list[str]   = []
    profanity             = False
    for a in assessments:
        sip = a.get("sensitiveInformationPolicy", {})
        for p in sip.get("piiEntities", []):
            if p.get("action") not in ("NONE", None):
                label = _PII_TYPE_LABELS.get(p["type"], p["type"])
                if label not in pii_types:
                    pii_types.append(label)
        for rx in sip.get("regexes", []):
            if rx.get("action") not in ("NONE", None):
                label = rx.get("name") or rx.get("regex") or "Regex"
                if label not in pii_types:
                    pii_types.append(label)
        for f in a.get("contentPolicy", {}).get("filters", []):
            if f.get("action") not in ("NONE", None):
                label = _CONTENT_LABELS.get(f["type"], f["type"])
                conf  = f.get("confidence", "")
                entry = f"{label} ({conf})" if conf else label
                if entry not in content:
                    content.append(entry)
        if a.get("wordPolicy", {}).get("managedWordLists"):
            profanity = True
    return {"pii_types": pii_types, "content": content, "profanity": profanity}


def sanitize_output(text: str, field: str = "") -> tuple[str, dict]:
    """
    Sanitiza o texto de saída removendo/anonimizando dados sensíveis.
    Retorna (texto_sanitizado, meta) onde meta descreve o que foi encontrado/alterado.
    """
    meta: dict = {"field": field, "bedrock_intervened": False, "pii": {}}

    if not text:
        return text, meta

    if settings.GUARDRAIL_ID_OUTPUT or settings.GUARDRAIL_ID:
        try:
            r = _apply("OUTPUT", text)
            outputs = r["outputs"]
            text = outputs[0].get("text", text) if outputs else text
            if r["action"] == "GUARDRAIL_INTERVENED":
                meta["bedrock_intervened"] = True
                meta["bedrock_detail"]     = _extract_output_detail(r["assessments"])
                logger.info("guardrail OUTPUT interveio campo=%s detail=%s", field, meta["bedrock_detail"])
        except Exception:
            logger.exception("erro Bedrock guardrail OUTPUT campo=%s — fallback regex", field)

    text, pii = _regex_sanitize(text)
    meta["pii"] = pii
    return text, meta


def _regex_sanitize(text: str) -> tuple[str, dict]:
    text, n_cpf     = _CPF_RE.subn("[CPF OMITIDO]", text)
    text, n_card    = _CARD_RE.subn("[CARTÃO OMITIDO]", text)
    text, n_account = _ACCOUNT_RE.subn("[CONTA OMITIDA]", text)
    text, n_nome    = _NOME_RE.subn(r'\1[NOME OMITIDO]', text)
    meta = {}
    if n_cpf:     meta["cpf"]     = n_cpf
    if n_card:    meta["cartao"]  = n_card
    if n_account: meta["conta"]   = n_account
    if n_nome:    meta["nome"]    = n_nome
    return text, meta
