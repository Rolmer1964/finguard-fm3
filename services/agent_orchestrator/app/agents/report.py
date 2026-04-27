def consolidate(triage: dict, risk: dict) -> dict:
    """Consolida triagem + risco em um payload final estruturado.

    Não chama LLM aqui — montar JSON é determinístico e mais barato.
    """
    return {
        "blocked": False,
        "category": triage.get("category"),
        "product": triage.get("product"),
        "sentiment": triage.get("sentiment"),
        "urgency": triage.get("urgency"),
        "summary": triage.get("summary"),
        "risk_level": risk.get("risk_level"),
        "risk_justification": risk.get("risk_justification"),
    }
