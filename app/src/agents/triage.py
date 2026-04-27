import logging

from ..llm import invoke_claude, parse_json_object
from ..profanity import mask
from ..settings import settings

logger = logging.getLogger("agent.triage")


SYSTEM_PROMPT = """Você é um analista de triagem de reclamações bancárias. Classifique a reclamação do cliente nos campos pedidos.

Categorias permitidas: "Cobrança Indevida", "Atendimento", "Fraude/Segurança", "Produto/Serviço", "Cancelamento", "Outros".
Produtos permitidos: "Cartão de Crédito", "Conta Corrente", "Empréstimo", "Investimentos", "Seguros", "Não Identificado".
Sentimentos: "Positivo", "Neutro", "Negativo", "Crítico".
Urgências: "Baixa", "Média", "Alta", "Crítica".

Regras:
- Resumo em 2-3 linhas, em português, tom profissional e neutro.
- NÃO inclua dados sensíveis (CPF, número de cartão, conta) no resumo.
- Substitua palavras impróprias por "***" no resumo.
- Responda APENAS com JSON neste formato:
{
  "categoria": "...",
  "produto": "...",
  "sentimento": "...",
  "urgencia": "...",
  "resumo": "..."
}"""


def run_triage(text: str, product_hint: str | None) -> dict:
    user = f"Texto da reclamação:\n\n{text}\n"
    if product_hint:
        user += f"\nProduto sugerido pelo canal de origem: {product_hint}\n"
    user += "\nResponda apenas com o JSON solicitado."

    raw = invoke_claude(settings.BEDROCK_MODEL_TRIAGE, SYSTEM_PROMPT, user, max_tokens=600, temperature=0.1)
    try:
        data = parse_json_object(raw)
    except Exception:
        logger.exception("falha ao parsear triagem; raw=%r", raw)
        data = {}

    return {
        "category": data.get("categoria") or "Outros",
        "product": data.get("produto") or product_hint or "Não Identificado",
        "sentiment": data.get("sentimento") or "Neutro",
        "urgency": data.get("urgencia") or "Baixa",
        "summary": mask(data.get("resumo") or ""),
    }
