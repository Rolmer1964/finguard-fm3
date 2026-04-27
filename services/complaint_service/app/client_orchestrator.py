import logging

import httpx

from .settings import settings

logger = logging.getLogger("complaints.orchestrator")


def analyze_complaint(complaint_id: str, text: str, product_hint: str | None = None) -> dict:
    """Chamada síncrona ao agent_orchestrator. Retorna o payload de análise.

    Em caso de falha, devolve um payload com `blocked=False` e os campos vazios para
    que a reclamação seja persistida mesmo que a análise falhe (status=Falha).
    """
    url = f"{settings.ORCHESTRATOR_URL.rstrip('/')}/analyze"
    payload = {"complaint_id": complaint_id, "text": text, "product_hint": product_hint}
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.exception("orchestrator call failed for %s: %s", complaint_id, exc)
        return {"error": str(exc)}
