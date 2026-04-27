import logging

from fastapi import APIRouter
from pydantic import BaseModel

from .graph import get_graph
from .guardrails.input_guard import POLITE_BLOCK_MESSAGE

router = APIRouter()
logger = logging.getLogger("orchestrator.routes")


class AnalyzeRequest(BaseModel):
    complaint_id: str
    text: str
    product_hint: str | None = None


@router.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict:
    state = {
        "complaint_id": payload.complaint_id,
        "text": payload.text,
        "product_hint": payload.product_hint,
    }
    final_state = get_graph().invoke(state)

    if final_state.get("blocked"):
        return {
            "blocked": True,
            "block_reason": final_state.get("block_reason") or POLITE_BLOCK_MESSAGE,
            "category": None,
            "product": None,
            "sentiment": None,
            "urgency": None,
            "summary": None,
            "risk_level": None,
            "risk_justification": None,
        }

    final = final_state.get("final", {})
    return {"blocked": False, **final}


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "orchestrator"}
