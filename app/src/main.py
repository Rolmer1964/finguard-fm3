
import csv
import io
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime as _dt
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .graph import analyze, clear_traces, get_traces
from .helpers import bar_width_px, compute_stats, count_output_files, pill_html, rag_vector_count
from .models import AnalyzeRequest
from .profanity import mask as mask_profanity
from .rag.ingest import ingest_all
from .rag.retriever import _store as _rag_store
from .report_writer import write_outputs
from .settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")

_LEVEL_STYLE = {
    "crít": "color:#991b1b;font-weight:600", "alt": "color:#9a3412;font-weight:600",
    "méd":  "color:#92400e", "med": "color:#92400e", "baix": "color:#065f46",
}


# ── Startup / lifespan ────────────────────────────────────────────────────────

_ingest_state: dict = {"status": "idle", "stats": None, "error": None}


def _run_ingest() -> None:
    global _ingest_state
    _ingest_state = {"status": "running", "stats": None, "error": None}
    logger.info("RAG: ingestão iniciada (thread=%s)", threading.current_thread().name)
    try:
        stats = ingest_all()
        _rag_store.cache_clear()
        _ingest_state = {"status": "done", "stats": stats.as_dict(), "error": None}
        logger.info(
            "RAG: ingestão concluída — %d vetores | adicionados=%d ignorados=%d",
            stats.total_vectors_after, stats.chunks_added, len(stats.skipped),
        )
    except Exception as exc:
        _ingest_state = {"status": "error", "stats": None, "error": str(exc)}
        logger.exception("RAG: falha na ingestão")


@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=_run_ingest, daemon=True, name="rag-startup").start()
    yield


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="FinGuard - Nível 3 (Arquiteto da Solução)", version="0.1.0", lifespan=lifespan)

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.filters["tojson"] = lambda v, indent=None: __import__("json").dumps(
    v, ensure_ascii=False, indent=indent
)
app.mount("/output", StaticFiles(directory=settings.OUTPUT_DIR, check_dir=False), name="output")
app.mount("/assets/hackathon", StaticFiles(directory=str(BASE.parent / "assets" / "hackathon"), check_dir=False), name="hackathon")

_ADR_PATH = BASE.parent / "assets" / "adr.html"


# ── Rotas: páginas principais ─────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html.j2", {"request": request})


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


# ── Rotas: análise ────────────────────────────────────────────────────────────

@app.post("/analyze")
def analyze_one(payload: AnalyzeRequest) -> JSONResponse:
    """Executa o grafo (triage → risk → report) numa reclamação e devolve o JSON consolidado."""
    return JSONResponse(analyze(payload.text, payload.product_hint))


@app.post("/analyze-form", response_class=HTMLResponse)
def analyze_from_form(request: Request, text: str = Form(...), product_hint: str = Form("")):
    result = analyze(text, product_hint or None)
    return templates.TemplateResponse(
        "result.html.j2",
        {"request": request, "result": result, "texto_original": mask_profanity(text)},
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
        canal   = (row.get("canal") or "").strip() or "Não informado"
        rec_id  = (row.get("id") or f"REC-{i:05d}")
        try:
            r = analyze(texto, produto_hint)
        except Exception as exc:
            logger.exception("[%s] falha ao analisar linha %d", rec_id, i)
            r = {"category": "Outros", "product": "Não Identificado",
                 "sentiment": "Neutro", "urgency": "Baixa", "summary": f"[falha: {exc}]",
                 "risk_level": "Baixo", "risk_justification": ""}
        if r.get("blocked"):
            logger.warning("[%s] linha %d bloqueada pelo guardrail", rec_id, i)
            r = {"category": "Bloqueado", "product": "Não Identificado",
                 "sentiment": "Neutro", "urgency": "Baixa",
                 "summary": "[Entrada bloqueada pelo guardrail de proteção]",
                 "risk_level": "Bloqueado", "risk_justification": r.get("message", "")}
        results.append({"id": rec_id, "canal": canal, "texto_original": mask_profanity(texto), **r})

    stem = _dt.utcnow().strftime("report_%Y-%m-%d-%H-%M-%S")
    paths = write_outputs(results, stem=stem)
    return RedirectResponse(url=f"/output/{Path(paths['html']).name}", status_code=303)


# ── Rotas: ingestão RAG ───────────────────────────────────────────────────────

@app.post("/ingest")
def ingest_docs(background_tasks: BackgroundTasks) -> JSONResponse:
    """Dispara re-ingestão em background. Consulte GET /ingest/status para acompanhar."""
    if _ingest_state["status"] == "running":
        return JSONResponse({"status": "already_running"}, status_code=409)
    background_tasks.add_task(_run_ingest)
    return JSONResponse({"status": "started", "message": "Ingestão iniciada. Consulte /ingest/status."}, status_code=202)


@app.get("/ingest/status")
def ingest_status() -> JSONResponse:
    """Retorna o estado atual da ingestão RAG."""
    return JSONResponse(_ingest_state)


# ── Rotas: admin ──────────────────────────────────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    docs = [d.name for d in Path(settings.RAG_DOCS_DIR).iterdir() if d.is_file()]
    guardrail_id = settings.GUARDRAIL_ID or None
    return templates.TemplateResponse("admin.html.j2", {
        "request":      request,
        "n_out":        count_output_files(),
        "n_vec":        rag_vector_count(),
        "n_traces":     len(get_traces()),
        "docs":         docs,
        "guardrail_id": guardrail_id,
        "guardrail_ver": settings.GUARDRAIL_VERSION if guardrail_id else "—",
    })


@app.post("/admin/reset")
def admin_reset(target: str = "all") -> JSONResponse:
    """Zera componentes do sistema. target: all | outputs | index | traces."""
    do_outputs = target in ("all", "outputs")
    do_index   = target in ("all", "index")
    do_traces  = target in ("all", "traces")

    removed_outputs = 0
    removed_index   = 0
    cleared_traces  = 0

    if do_outputs:
        for f in Path(settings.OUTPUT_DIR).glob("*"):
            if f.is_file():
                f.unlink()
                removed_outputs += 1

    if do_index:
        for f in Path(settings.RAG_INDEX_DIR).glob("*"):
            if f.is_file():
                f.unlink()
                removed_index += 1
        _rag_store.cache_clear()

    if do_traces:
        cleared_traces = clear_traces()

    logger.info(
        "admin/reset target=%s: outputs=%d index_files=%d traces=%d",
        target, removed_outputs, removed_index, cleared_traces,
    )
    return JSONResponse({
        "target": target,
        "removed_output_files": removed_outputs,
        "removed_index_files": removed_index,
        "cleared_traces": cleared_traces,
        "status": "ok",
    })


# ── Rotas: relatórios ─────────────────────────────────────────────────────────

@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request):
    out_dir    = Path(settings.OUTPUT_DIR)
    html_files = sorted(out_dir.glob("*.html"), reverse=True)
    reports = [
        {
            "stem":       f.stem,
            "ts_display": f.stem,
            "size_kb":    round(f.stat().st_size / 1024, 1),
            "has_json":   (out_dir / f"{f.stem}.json").exists(),
            "has_csv":    (out_dir / f"{f.stem}.csv").exists(),
            "has_md":     (out_dir / f"{f.stem}.md").exists(),
        }
        for f in html_files
    ]
    return templates.TemplateResponse("reports.html.j2", {
        "request": request,
        "reports": reports,
        "total":   len(html_files),
    })


# ── Rotas: traces / log ───────────────────────────────────────────────────────

@app.get("/traces", response_class=HTMLResponse)
def traces_page(request: Request):
    data = get_traces()

    series: dict[str, list[float]] = {"total_ms": [], "triage": [], "risk": [], "report": []}
    for t in data:
        tm = t.get("timings_ms", {})
        series["total_ms"].append(float(t.get("total_ms") or 0))
        series["triage"].append(float(tm.get("triage") or 0))
        series["risk"].append(float(tm.get("risk") or 0))
        series["report"].append(float(tm.get("report") or 0))

    st = {k: compute_stats(v) for k, v in series.items()}

    traces_display = []
    for t in data:
        tm      = t.get("timings_ms", {})
        t_ms    = int(tm.get("triage",          0) or 0)
        r_ms    = int(tm.get("risk",            0) or 0)
        rp_ms   = int(tm.get("report",          0) or 0)
        gi_ms   = int(tm.get("guardrail_input", 0) or 0)
        total   = int(t.get("total_ms", t_ms + r_ms + rp_ms))
        traces_display.append({
            **t,
            "t_ms":            t_ms,
            "r_ms":            r_ms,
            "rp_ms":           rp_ms,
            "gi_ms":           gi_ms,
            "total_display":   gi_ms + total,
            "bar_triage":      bar_width_px(t_ms,  total),
            "bar_risk":        bar_width_px(r_ms,  total),
            "bar_report":      bar_width_px(rp_ms, total),
            "urgency_html":    pill_html(t.get("urgency"),    _LEVEL_STYLE),
            "risk_level_html": pill_html(t.get("risk_level"), _LEVEL_STYLE),
        })

    return templates.TemplateResponse("traces.html.j2", {
        "request":  request,
        "count":    len(data),
        "st":       st,
        "has_data": bool(data),
        "traces":   traces_display,
    })


# ── Rotas: documentação ───────────────────────────────────────────────────────

@app.get("/adr", response_class=HTMLResponse)
def adr_page():
    if _ADR_PATH.exists():
        return HTMLResponse(_ADR_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<p>ADR não encontrado em assets/adr.html</p>", status_code=404)
