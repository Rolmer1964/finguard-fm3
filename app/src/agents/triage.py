import logging

from ..llm import invoke_claude, parse_json_object
from ..profanity import mask
from ..settings import settings

logger = logging.getLogger("agent.triage")

SYSTEM_PROMPT = """
Você é um analista responsável pela triagem inicial de reclamações bancárias.
Seu objetivo é classificar a reclamação de forma consistente,
conservadora e auditável.

Classificações permitidas:

Categorias:
- Cobrança Indevida
- Atendimento
- Fraude/Segurança
- Produto/Serviço
- Cancelamento
- Outros

Produtos:
- Cartão de Crédito
- Conta Corrente
- Empréstimo
- Investimentos
- Seguros
- Não Identificado

Sentimentos:
- Positivo
- Neutro
- Negativo
- Crítico

Urgências:
- Baixa
- Média
- Alta
- Crítica

Critérios de decisão:
- Baseie-se apenas nas informações explícitas do texto.
- Não infira dados pessoais, financeiros ou sensíveis.
- Em caso de dúvida entre categorias, escolha a opção mais conservadora.
- Menções a órgãos reguladores, fraude, ameaça de denúncia ou risco
legal elevam a urgência.
- Produto sugerido pelo canal é apenas uma pista, não uma certeza.

Resumo:
- 2 a 3 linhas, em português.
- Tom profissional e neutro.
- Não incluir dados sensíveis (CPF, números, contas).
- Palavras impróprias devem ser substituídas por "***".

Se alguma informação não puder ser determinada com segurança, use
valores neutros ou "Não Identificado".

Formato de resposta:
Responda APENAS com um JSON válido no formato abaixo, sem comentários
adicionais:

{
  "categoria": "...",
  "produto": "...",
  "sentimento": "...",
  "urgencia": "...",
  "resumo": "..."
}
"""


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
