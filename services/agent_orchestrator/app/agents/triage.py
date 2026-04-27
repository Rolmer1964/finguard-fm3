import logging
import re

from ..llm import invoke_claude, parse_json_object
from ..settings import settings

logger = logging.getLogger("orchestrator.triage")

PALAVROES = [
    r"\bporra\b", r"\bmerda\b", r"\bcaralho\b", r"\bdroga\b",
    r"\bidiota\b", r"\bimbecil\b", r"\bfdp\b", r"\bbosta\b",
]
PALAVROES_RE = re.compile("|".join(PALAVROES), re.IGNORECASE)


SYSTEM_PROMPT = """Você é um analista de triagem de reclamações bancárias. Classifique a reclamação do cliente nos campos pedidos.

Categorias permitidas: "Cobrança Indevida", "Atendimento", "Fraude/Segurança", "Produto/Serviço", "Cancelamento", "Outros".
Produtos permitidos: "Cartão de Crédito", "Conta Corrente", "Empréstimo", "Investimentos", "Seguros", "Não Identificado".
Sentimentos: "Positivo", "Neutro", "Negativo", "Crítico".
Urgências: "Baixa", "Média", "Alta", "Crítica".

Regras:
- Resumo em 2-3 linhas, em português, tom profissional e neutro.
- NÃO inclua dados sensíveis (CPF, número de cartão, conta) no resumo.
- Substitua palavras impróprias por "***" no resumo.
- Responda APENAS com JSON no formato:
{
  "categoria": "...",
  "produto": "...",
  "sentimento": "...",
  "urgencia": "...",
  "resumo": "..."
}"""


def _mask_profanity(text: str) -> str:
    return PALAVROES_RE.sub("***", text or "")


def run_triage(text: str, product_hint: str | None) -> dict:
    user = f"Texto da reclamação:\n\n{text}\n\n"
    if product_hint:
        user += f"Produto sugerido pelo canal de origem: {product_hint}\n"
    user += "\nResponda apenas com o JSON solicitado."

    raw = invoke_claude(settings.BEDROCK_MODEL_TRIAGE, SYSTEM_PROMPT, user, max_tokens=600, temperature=0.1)
    try:
        data = parse_json_object(raw)
    except Exception:
        logger.exception("falha ao parsear triagem; raw=%r", raw)
        data = {}

    return {
        "category": data.get("categoria"),
        "product": data.get("produto") or product_hint or "Não Identificado",
        "sentiment": data.get("sentimento"),
        "urgency": data.get("urgencia"),
        "summary": _mask_profanity(data.get("resumo") or ""),
    }
