from typing import Any

from pydantic import BaseModel, Field


class ComplaintCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    channel: str | None = None
    product_hint: str | None = None
    external_id: str | None = None


class ComplaintBulkCreate(BaseModel):
    items: list[ComplaintCreate]


class AnalysisOut(BaseModel):
    blocked: bool = False
    block_reason: str | None = None
    category: str | None = None
    product: str | None = None
    sentiment: str | None = None
    urgency: str | None = None
    summary: str | None = None
    risk_level: str | None = None
    risk_justification: str | None = None


class ComplaintOut(BaseModel):
    id: str
    external_id: str | None
    raw_text: str
    channel: str | None
    product_hint: str | None
    status: str
    created_at: str
    analysis: AnalysisOut | None = None


class BulkResult(BaseModel):
    created: int
    analyzed: int
    failed: int
    details: list[dict[str, Any]] = []
