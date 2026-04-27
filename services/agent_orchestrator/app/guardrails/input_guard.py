import logging

from ..llm import apply_guardrail

logger = logging.getLogger("orchestrator.input_guard")

POLITE_BLOCK_MESSAGE = (
    "Não foi possível processar essa entrada. Por favor, descreva sua reclamação "
    "de forma clara e objetiva, sem instruções ao sistema, ameaças ou conteúdo "
    "que não se relacione a um problema com produto ou serviço financeiro."
)


def check_input(text: str) -> dict:
    """Aplica o guardrail Bedrock no texto de entrada.

    Retorna {'allowed': bool, 'reason': str | None}.
    """
    try:
        resp = apply_guardrail(text, source="INPUT")
    except Exception as exc:
        logger.exception("falha aplicando input guardrail: %s", exc)
        return {"allowed": True, "reason": None}

    action = resp.get("action", "NONE")
    if action == "GUARDRAIL_INTERVENED":
        outputs = resp.get("outputs") or []
        reason = outputs[0].get("text") if outputs else None
        return {"allowed": False, "reason": reason or POLITE_BLOCK_MESSAGE}
    return {"allowed": True, "reason": None}
