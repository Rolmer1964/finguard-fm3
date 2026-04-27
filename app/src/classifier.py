import json
import logging
import re

import boto3

from .profanity import mask
from .settings import settings

logger = logging.getLogger("classifier")


SYSTEM_PROMPT = """Você é um analista de triagem de reclamações bancárias. Classifique a reclamação do cliente nos campos pedidos.

Categorias permitidas: "Cobrança Indevida", "Atendimento", "Fraude/Segurança", "Produto/Serviço", "Cancelamento", "Outros".
Produtos permitidos: "Cartão de Crédito", "Conta Corrente", "Empréstimo", "Investimentos", "Seguros", "Não Identificado".
Sentimentos: "Positivo", "Neutro", "Negativo", "Crítico".
Urgências: "Baixa", "Média", "Alta", "Crítica".

Regras:
- Resumo em 2-3 linhas, em português, tom profissional e neutro, em linguagem padronizada.
- Substitua palavras impróprias por "***" no resumo.
- NÃO inclua dados sensíveis (CPF, número de cartão, conta) no resumo.
- Responda APENAS com JSON válido neste formato exato:
{
  "categoria": "...",
  "produto": "...",
  "sentimento": "...",
  "urgencia": "...",
  "resumo": "..."
}"""


def _client():
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        aws_session_token=settings.AWS_SESSION_TOKEN or None,
    )


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)
    return json.loads(cleaned)


def classify(text: str, product_hint: str | None = None) -> dict:
    """Faz UMA chamada ao Bedrock e devolve o dict com os 5 campos."""
    user = f"Texto da reclamação:\n\n{text}\n"
    if product_hint:
        user += f"\nProduto sugerido pelo canal: {product_hint}\n"
    user += "\nResponda apenas com o JSON solicitado."

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 600,
        "temperature": 0.1,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user}],
    }

    resp = _client().invoke_model(
        modelId=settings.BEDROCK_MODEL_ID,
        accept="application/json",
        contentType="application/json",
        body=json.dumps(body),
    )
    payload = json.loads(resp["body"].read())
    raw_text = "".join(p.get("text", "") for p in payload.get("content", []) if p.get("type") == "text").strip()

    try:
        data = _parse_json_object(raw_text)
    except Exception:
        logger.exception("falha ao parsear resposta do modelo; raw=%r", raw_text)
        data = {}

    return {
        "categoria": data.get("categoria") or "Outros",
        "produto": data.get("produto") or product_hint or "Não Identificado",
        "sentimento": data.get("sentimento") or "Neutro",
        "urgencia": data.get("urgencia") or "Baixa",
        "resumo": mask(data.get("resumo") or ""),
    }
