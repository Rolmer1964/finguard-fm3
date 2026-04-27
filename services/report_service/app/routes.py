from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from .adr_builder import render_adr, write_adr
from .dashboard import build_dashboard
from .db import get_db
from .html_report import render_report, write_report

router = APIRouter()


def _public_dashboard(d: dict) -> dict:
    """Remove o campo 'rows' (texto bruto) do retorno público — esses dados ficam no relatório HTML."""
    return {k: v for k, v in d.items() if k != "rows"}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> JSONResponse:
    data = build_dashboard(db)
    return JSONResponse(_public_dashboard(data))


@router.get("/html")
def html_report(save: bool = False, db: Session = Depends(get_db)):
    data = build_dashboard(db)
    html = render_report(data)
    if save:
        path = write_report(data)
        return JSONResponse({"saved_to": path})
    return HTMLResponse(html)


@router.get("/adr")
def adr(save: bool = False, db: Session = Depends(get_db)):
    data = build_dashboard(db)
    html = render_adr(data)
    if save:
        path = write_adr(data)
        return JSONResponse({"saved_to": path})
    return HTMLResponse(html)


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "reports"}
