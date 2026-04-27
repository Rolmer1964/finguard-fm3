import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .client_orchestrator import analyze_complaint
from .db import get_db
from .models import Analysis, Complaint
from .schemas import (
    AnalysisOut,
    BulkResult,
    ComplaintBulkCreate,
    ComplaintCreate,
    ComplaintOut,
)

router = APIRouter()
logger = logging.getLogger("complaints.routes")


def _to_out(c: Complaint) -> ComplaintOut:
    a = c.analysis
    analysis_out = None
    if a is not None:
        analysis_out = AnalysisOut(
            blocked=a.blocked,
            block_reason=a.block_reason,
            category=a.category,
            product=a.product,
            sentiment=a.sentiment,
            urgency=a.urgency,
            summary=a.summary,
            risk_level=a.risk_level,
            risk_justification=a.risk_justification,
        )
    return ComplaintOut(
        id=str(c.id),
        external_id=c.external_id,
        raw_text=c.raw_text,
        channel=c.channel,
        product_hint=c.product_hint,
        status=c.status,
        created_at=c.created_at.isoformat() if c.created_at else "",
        analysis=analysis_out,
    )


def _persist_analysis(db: Session, complaint: Complaint, payload: dict) -> None:
    if "error" in payload and not payload.get("blocked"):
        complaint.status = "Falha"
        db.commit()
        return

    blocked = bool(payload.get("blocked"))
    analysis = Analysis(
        complaint_id=complaint.id,
        blocked=blocked,
        block_reason=payload.get("block_reason"),
        category=payload.get("category"),
        product=payload.get("product"),
        sentiment=payload.get("sentiment"),
        urgency=payload.get("urgency"),
        summary=payload.get("summary"),
        risk_level=payload.get("risk_level"),
        risk_justification=payload.get("risk_justification"),
        raw_payload=payload,
    )
    complaint.status = "Bloqueada" if blocked else "Resolvida"
    db.add(analysis)
    db.commit()


@router.post("/", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def create_complaint(
    payload: ComplaintCreate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
):
    complaint = Complaint(
        raw_text=payload.text,
        channel=payload.channel,
        product_hint=payload.product_hint,
        external_id=payload.external_id,
        created_by_user_id=x_user_id,
        status="Em análise",
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    result = analyze_complaint(str(complaint.id), payload.text, payload.product_hint)
    _persist_analysis(db, complaint, result)
    db.refresh(complaint)
    return _to_out(complaint)


@router.post("/bulk", response_model=BulkResult)
def bulk_create(
    payload: ComplaintBulkCreate,
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
):
    created = analyzed = failed = 0
    details: list[dict] = []
    for item in payload.items:
        complaint = Complaint(
            raw_text=item.text,
            channel=item.channel,
            product_hint=item.product_hint,
            external_id=item.external_id,
            created_by_user_id=x_user_id,
            status="Em análise",
        )
        db.add(complaint)
        db.commit()
        db.refresh(complaint)
        created += 1
        try:
            result = analyze_complaint(str(complaint.id), item.text, item.product_hint)
            _persist_analysis(db, complaint, result)
            if "error" in result and not result.get("blocked"):
                failed += 1
                details.append({"id": str(complaint.id), "error": result["error"]})
            else:
                analyzed += 1
        except Exception as exc:
            failed += 1
            complaint.status = "Falha"
            db.commit()
            details.append({"id": str(complaint.id), "error": str(exc)})
    return BulkResult(created=created, analyzed=analyzed, failed=failed, details=details)


@router.get("/", response_model=list[ComplaintOut])
def list_complaints(db: Session = Depends(get_db), limit: int = 100, offset: int = 0):
    rows = db.execute(
        select(Complaint).order_by(Complaint.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return [_to_out(c) for c in rows]


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: str, db: Session = Depends(get_db)):
    c = db.get(Complaint, complaint_id)
    if not c:
        raise HTTPException(status_code=404, detail="Reclamação não encontrada")
    return _to_out(c)


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "complaints"}
