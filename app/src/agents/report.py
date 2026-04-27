def consolidate(triage: dict, risk: dict) -> dict:
    """Consolida triagem + risco em payload final estruturado.

    Sem chamada a LLM aqui: agregação determinística é mais barata e
    mais previsível para uma etapa de consolidação.
    """
    return {
        "category": triage.get("category"),
        "product": triage.get("product"),
        "sentiment": triage.get("sentiment"),
        "urgency": triage.get("urgency"),
        "summary": triage.get("summary"),
        "risk_level": risk.get("risk_level"),
        "risk_justification": risk.get("risk_justification"),
    }
