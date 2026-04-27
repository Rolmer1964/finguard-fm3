import logging

from ..llm import invoke_claude, parse_json_object
from ..rag.policy_loader import load_policy
from ..settings import settings

logger = logging.getLogger("orchestrator.risk")


SYSTEM_PROMPT = """Você é um analista de risco e conformidade de uma instituição financeira.
Avalie a reclamação à luz da Política Interna fornecida e da triagem prévia.

Avalie:
- Indícios de fraude ou transação não autorizada
- Violação de regulamentos (LGPD, sigilo bancário)
- Risco reputacional (imprensa, redes sociais, órgãos reguladores)
- Necessidade de escalação imediata

Níveis de risco permitidos: "Baixo", "Médio", "Alto", "Crítico".
A justificativa deve ter 2-3 frases, em português, tom profissional. NÃO inclua dados sensíveis.

Responda APENAS com JSON:
{
  "risco": "...",
  "justificativa": "..."
}"""


def run_risk(text: str, triage: dict) -> dict:
    policy = load_policy()
    user = f"""Política Interna (referência):
\"\"\"
{policy}
\"\"\"

Triagem prévia:
- Categoria: {triage.get('category')}
- Produto: {triage.get('product')}
- Sentimento: {triage.get('sentiment')}
- Urgência: {triage.get('urgency')}
- Resumo: {triage.get('summary')}

Texto original da reclamação:
\"\"\"
{text}
\"\"\"

Avalie o risco e justifique. Responda apenas com o JSON solicitado."""

    raw = invoke_claude(settings.BEDROCK_MODEL_RISK, SYSTEM_PROMPT, user, max_tokens=600, temperature=0.2)
    try:
        data = parse_json_object(raw)
    except Exception:
        logger.exception("falha ao parsear risco; raw=%r", raw)
        data = {}

    return {
        "risk_level": data.get("risco"),
        "risk_justification": data.get("justificativa"),
    }
