_SLA_POR_URGENCIA: dict[str, str] = {
    "Baixa":   "5 dias úteis",
    "Média":   "3 dias úteis",
    "Alta":    "24 horas",
    "Crítica": "4 horas",
}

_AREA_POR_PRODUTO: dict[str, str] = {
    "Cartão de Crédito": "Gerência de Cartões",
    "Conta Corrente":    "Gerência de Contas",
    "Empréstimo":        "Gerência de Crédito",
    "Investimentos":     "Gerência de Investimentos",
    "Seguros":           "Gerência de Seguros",
}

# Canais que exigem urgência CRÍTICA automática (POL-SAC-001 §4.3)
_CANAIS_CRITICOS: set[str] = {"Banco Central", "Procon", "Justiça"}

# Urgência mínima garantida por nível de risco
_URGENCIA_ORDEM: dict[str, int] = {"Crítica": 4, "Alta": 3, "Média": 2, "Baixa": 1}
_RISCO_URGENCIA_MINIMA: dict[str, str] = {"Crítico": "Alta"}


def consolidate(triage: dict, risk: dict, canal: str | None = None) -> dict:
    urgency = triage.get("urgency")
    product = triage.get("product")

    # Override 1: canal regulatório → urgência CRÍTICA obrigatória (POL-SAC-001 §4.3)
    if canal in _CANAIS_CRITICOS and urgency != "Crítica":
        urgency = "Crítica"

    # Override 2: risco Crítico garante urgência mínima Alta (segunda linha de defesa)
    risco_min = _RISCO_URGENCIA_MINIMA.get(risk.get("risk_level") or "")
    if risco_min and _URGENCIA_ORDEM.get(urgency or "", 0) < _URGENCIA_ORDEM[risco_min]:
        urgency = risco_min

    return {
        "category":           triage.get("category"),
        "product":            product,
        "sentiment":          triage.get("sentiment"),
        "urgency":            urgency,
        "summary":            triage.get("summary"),
        "prazo_resposta":     _SLA_POR_URGENCIA.get(urgency or ""),
        "area_responsavel":   _AREA_POR_PRODUTO.get(product or "", "Área de Suporte Geral"),
        "risk_level":         risk.get("risk_level"),
        "risk_justification": risk.get("risk_justification"),
        "acoes_recomendadas": risk.get("acoes_recomendadas", []),
    }
