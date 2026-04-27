import logging

from ..llm import invoke_claude, parse_json_object
from ..rag.retriever import format_for_prompt, retrieve
from ..settings import settings

logger = logging.getLogger("agent.risk")


SYSTEM_PROMPT = """Você é um analista de risco e conformidade de uma instituição financeira.
Avalie a reclamação à luz dos trechos relevantes da Política Interna fornecida e da triagem prévia.

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


def _build_query(text: str, triage: dict) -> str:
    """Concatena texto + dimensões da triagem para uma busca semântica mais focada."""
    bits = [text]
    for k in ("category", "product", "sentiment"):
        v = triage.get(k)
        if v:
            bits.append(str(v))
    return " ".join(bits)


def run_risk(text: str, triage: dict) -> dict:
    chunks = retrieve(_build_query(text, triage), k=settings.RAG_TOP_K)
    policy_context = format_for_prompt(chunks) or "(nenhum trecho da política interna disponível — índice vazio)"

    user = f"""{policy_context}

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

Avalie o risco e justifique com base nos trechos da política. Responda apenas com o JSON solicitado."""

    raw = invoke_claude(settings.BEDROCK_MODEL_RISK, SYSTEM_PROMPT, user, max_tokens=500, temperature=0.2)
    try:
        data = parse_json_object(raw)
    except Exception:
        logger.exception("falha ao parsear risco; raw=%r", raw)
        data = {}

    logger.info("risk usou %d trechos da política (top-k=%d)", len(chunks), settings.RAG_TOP_K)
    return {
        "risk_level": data.get("risco") or "Baixo",
        "risk_justification": data.get("justificativa") or "",
        "rag_chunks_used": len(chunks),
    }
