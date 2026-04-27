import csv
import io
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .graph import analyze
from .report_writer import write_outputs
from .settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")

app = FastAPI(title="FinGuard - Nível 2 (Orquestrador)", version="0.1.0")

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/output", StaticFiles(directory=settings.OUTPUT_DIR, check_dir=False), name="output")


class AnalyzeRequest(BaseModel):
    text: str
    product_hint: str | None = None


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html.j2", {"request": request})


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
def analyze_one(payload: AnalyzeRequest) -> JSONResponse:
    """Executa o grafo (triage → risk → report) numa reclamação e devolve o JSON consolidado."""
    return JSONResponse(analyze(payload.text, payload.product_hint))


@app.post("/analyze-form", response_class=HTMLResponse)
def analyze_from_form(request: Request, text: str = Form(...), product_hint: str = Form("")):
    result = analyze(text, product_hint or None)
    return templates.TemplateResponse(
        "result.html.j2",
        {"request": request, "result": result, "texto_original": text},
    )


@app.post("/batch")
async def batch(file: UploadFile = File(...)) -> JSONResponse:
    """Processa um CSV (colunas: id, texto_reclamacao, produto opcional) através do grafo
    completo e gera JSON, CSV, MD e HTML em /output."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Envie um arquivo .csv")

    raw = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or "texto_reclamacao" not in reader.fieldnames:
        raise HTTPException(400, "CSV precisa ter ao menos a coluna 'texto_reclamacao'")

    results: list[dict] = []
    for i, row in enumerate(reader, start=1):
        texto = (row.get("texto_reclamacao") or "").strip()
        if not texto:
            continue
        produto_hint = (row.get("produto") or "").strip() or None
        rec_id = (row.get("id") or f"REC-{i:05d}")
        try:
            r = analyze(texto, produto_hint)
        except Exception as exc:
            logger.exception("[%s] falha ao analisar linha %d", rec_id, i)
            r = {"category": "Outros", "product": "Não Identificado",
                 "sentiment": "Neutro", "urgency": "Baixa", "summary": f"[falha: {exc}]",
                 "risk_level": "Baixo", "risk_justification": ""}
        results.append({"id": rec_id, "texto_original": texto, **r})

    paths = write_outputs(results, stem=Path(file.filename).stem)
    return JSONResponse({
        "processed": len(results),
        "outputs": paths,
        "view_html": f"/output/{Path(paths['html']).name}",
    })
