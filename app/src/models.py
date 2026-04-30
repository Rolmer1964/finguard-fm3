from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    text: str
    product_hint: str | None = None
