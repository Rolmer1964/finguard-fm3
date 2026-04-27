import csv
import io
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .classifier import classify
from .report_writer import write_outputs
from .settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")

app = FastAPI(title="FinGuard - Nível 1 (Classificador)", version="0.1.0")

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
app.mount("/output", StaticFiles(directory=settings.OUTPUT_DIR, check_dir=False), name="output")


class ClassifyRequest(BaseModel):
    text: str
    product_hint: str | None = None


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html.j2", {"request": request})


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/classify")
def classify_one(payload: ClassifyRequest) -> JSONResponse:
    result = classify(payload.text, payload.product_hint)
    return JSONResponse(result)


@app.post("/classify-form", response_class=HTMLResponse)
def classify_from_form(request: Request, text: str = Form(...), product_hint: str = Form("")):
    result = classify(text, product_hint or None)
    return templates.TemplateResponse(
        "result.html.j2",
        {"request": request, "result": result, "texto_original": text},
    )


@app.post("/batch")
async def batch(file: UploadFile = File(...)) -> JSONResponse:
    """Recebe um CSV com colunas id, texto_reclamacao, produto (opcional) e
    classifica cada linha. Gera JSON, CSV e HTML em /output e devolve os paths."""
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
        try:
            r = classify(texto, produto_hint)
        except Exception as exc:
            logger.exception("falha ao classificar linha %d", i)
            r = {"categoria": "Outros", "produto": "Não Identificado",
                 "sentimento": "Neutro", "urgencia": "Baixa",
                 "resumo": f"[falha de classificação: {exc}]"}
        results.append({
            "id": (row.get("id") or f"REC-{i:05d}"),
            "texto_original": texto,
            **r,
        })

    paths = write_outputs(results, stem=Path(file.filename).stem)
    return JSONResponse({
        "processed": len(results),
        "outputs": paths,
        "view_html": f"/output/{Path(paths['html']).name}",
    })
