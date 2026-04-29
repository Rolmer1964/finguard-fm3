
import asyncio
import concurrent.futures
import csv
import io
import json as _json
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime as _dt
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from .graph import analyze, clear_traces, get_traces, inject_trace, sum_timings
from .helpers import bar_width_px, compute_stats, count_output_files, pill_html, rag_vector_count
from .models import AnalyzeRequest
from .profanity import mask as mask_profanity
from .rag.ingest import ingest_all
from .rag.retriever import _store as _rag_store
from .report_writer import build_report_context, write_outputs
from .settings import now_brt, settings

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


def _recompose_all_traces() -> None:
    """Reconstrói o log de execução a partir de todos os relatórios JSON salvos."""
    out_dir = Path(settings.OUTPUT_DIR)
    json_files = sorted(
        [f for f in out_dir.glob("report_*.json") if not f.name.endswith(".meta.json")]
    )  # mais antigo primeiro → mais recente termina no topo do deque
    total = 0
    for json_file in json_files:
        try:
            items = _json.loads(json_file.read_text(encoding="utf-8"))
            if not isinstance(items, list):
                continue
            for item in reversed(items):
                texto = item.get("texto_original", "")
                tm = item.get("timings_ms", {})
                inject_trace({
                    "trace_id":     item.get("id", "?"),
                    "timestamp":    item.get("timestamp", json_file.stem),
                    "text_preview": (texto[:70] + "…") if len(texto) > 70 else texto,
                    "blocked":      item.get("blocked", False),
                    "category":     item.get("category"),
                    "urgency":      item.get("urgency"),
                    "risk_level":   item.get("risk_level"),
                    "timings_ms":   tm,
                    "total_ms":     sum_timings(tm),
                })
            total += len(items)
        except Exception:
            logger.exception("traces: falha ao recompor %s", json_file.name)
    logger.info("traces: recomposição automática — %d registros de %d arquivo(s)", total, len(json_files))


@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=_run_ingest, daemon=True, name="rag-startup").start()
    _recompose_all_traces()
    yield


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="FinGuard - Nível 3 (Arquiteto da Solução)", version="0.1.0", lifespan=lifespan)

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.filters["tojson"] = lambda v, indent=None: Markup(_json.dumps(v, ensure_ascii=False, indent=indent))
app.mount("/output", StaticFiles(directory=settings.OUTPUT_DIR, check_dir=False), name="output")
app.mount("/assets/hackathon", StaticFiles(directory=str(BASE.parent / "assets" / "hackathon"), check_dir=False), name="hackathon")
app.mount("/assets/images",        StaticFiles(directory=str(BASE.parent / "assets" / "images"),        check_dir=False), name="images")
app.mount("/assets/presentation",  StaticFiles(directory=str(BASE.parent / "assets" / "presentation"), check_dir=False), name="presentation")

_ADR_PATH = BASE.parent / "assets" / "adr.html"


# ── Helpers de processamento ─────────────────────────────────────────────────

def _analyze_with_retry(
    texto: str,
    produto_hint: str | None,
    rec_id: str,
    rate_limit_delay: float,
    max_retries: int,
) -> dict:
    if rate_limit_delay > 0:
        time.sleep(rate_limit_delay)
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return analyze(texto, produto_hint, record_id=rec_id)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "[%s] tentativa %d/%d falhou — retry em %ds: %s",
                    rec_id, attempt + 1, max_retries + 1, wait, exc,
                )
                time.sleep(wait)
    logger.error("[%s] todas %d tentativas falharam: %s", rec_id, max_retries + 1, last_exc)
    raise last_exc  # type: ignore[misc]


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
async def batch(file: UploadFile = File(...), label: str = Form("")) -> JSONResponse:
    """Processa um CSV em paralelo (ThreadPoolExecutor) com retry automático por registro."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Envie um arquivo .csv")

    raw = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or "texto_reclamacao" not in reader.fieldnames:
        raise HTTPException(400, "CSV precisa ter ao menos a coluna 'texto_reclamacao'")

    rows = []
    for i, row in enumerate(reader, start=1):
        texto = (row.get("texto_reclamacao") or "").strip()
        if not texto:
            continue
        rows.append({
            "texto":        texto,
            "produto_hint": (row.get("produto") or "").strip() or None,
            "canal":        (row.get("canal") or "").strip() or "Não informado",
            "rec_id":       (row.get("id") or f"REC-{i:05d}"),
        })

    t_start    = time.time()
    started_at = now_brt().strftime("%Y-%m-%d %H:%M:%S (UTC-3)")
    stem       = now_brt().strftime("report_%Y-%m-%d-%H-%M-%S")
    csv_name   = file.filename or None

    def _run_batch() -> str:
        failed_path = Path(settings.OUTPUT_DIR) / f"failed_{stem}.json"
        max_passes  = settings.BATCH_MAX_PASSES

        def _make_processor(delay: float, retries: int):
            def process_row(row_data: dict) -> dict:
                rec_id       = row_data["rec_id"]
                texto        = row_data["texto"]
                produto_hint = row_data["produto_hint"]
                canal        = row_data["canal"]
                try:
                    r = _analyze_with_retry(
                        texto=texto,
                        produto_hint=produto_hint,
                        rec_id=rec_id,
                        rate_limit_delay=delay,
                        max_retries=retries,
                    )
                except Exception as exc:
                    if "ThrottlingException" in str(exc) or "throttling" in str(exc).lower():
                        logger.warning("[%s] throttling — agendado para próximo passe", rec_id)
                        return {"_throttled": True, "_row": row_data}
                    logger.error("[%s] falha definitiva: %s", rec_id, exc)
                    r = {"category": "Erro", "product": "—", "sentiment": "—", "urgency": "—",
                         "summary": f"[falha: {exc}]", "risk_level": "—", "risk_justification": ""}
                else:
                    if r.get("blocked"):
                        logger.warning("[%s] bloqueada pelo guardrail reason=%s", rec_id, r.get("block_reason"))
                        r = {"category": "Bloqueado", "product": "—", "sentiment": "—", "urgency": "—",
                             "summary": "[Entrada bloqueada pelo guardrail de proteção]",
                             "risk_level": "Bloqueado", "risk_justification": r.get("message", ""),
                             "block_reason": r.get("block_reason", "")}
                return {"id": rec_id, "canal": canal, "texto_original": mask_profanity(texto), **r}
            return process_row

        workers  = settings.BATCH_MAX_WORKERS
        delay    = settings.BATCH_RATE_LIMIT_DELAY
        retries  = settings.BATCH_MAX_RETRIES
        pending  = rows
        all_results: list[dict] = []
        pass_stats: list[dict]  = []

        for pass_num in range(max_passes):
            if not pending:
                break

            if pass_num > 0:
                prev_rate = pass_stats[-1]["throttle_rate"]
                wait = settings.BATCH_RETRY_DELAY * (1.0 + prev_rate)
                logger.info("batch passe %d/%d: aguardando %.0fs (throttle_rate anterior=%.0f%%)",
                            pass_num + 1, max_passes, wait, prev_rate * 100)
                time.sleep(wait)

            logger.info("batch passe %d/%d: %d registros | workers=%d delay=%.2fs retries=%d",
                        pass_num + 1, max_passes, len(pending), workers, delay, retries)

            pass_start    = time.time()
            next_pending: list[dict] = []
            success_count = 0
            fn = _make_processor(delay, retries)
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                for result in executor.map(fn, pending):
                    if result.get("_throttled"):
                        next_pending.append(result["_row"])
                    else:
                        all_results.append(result)
                        success_count += 1

            pass_elapsed    = time.time() - pass_start
            throttled_count = len(next_pending)
            total_pass      = len(pending)
            throttle_rate   = throttled_count / total_pass if total_pass else 0.0
            throughput_rpm  = round(success_count / pass_elapsed * 60, 1) if pass_elapsed > 0 else 0.0

            pass_stats.append({
                "pass_num":      pass_num + 1,
                "workers":       workers,
                "delay_s":       round(delay, 2),
                "retries":       retries,
                "total":         total_pass,
                "success":       success_count,
                "throttled":     throttled_count,
                "throttle_rate": round(throttle_rate, 4),
                "throttle_pct":  round(throttle_rate * 100, 1),
                "duration_s":    round(pass_elapsed, 1),
                "throughput_rpm": throughput_rpm,
            })

            logger.info(
                "batch passe %d/%d: sucesso=%d throttled=%d (%.0f%%) | %.1fs | %.1f reg/min",
                pass_num + 1, max_passes, success_count, throttled_count,
                throttle_rate * 100, pass_elapsed, throughput_rpm,
            )

            if throttle_rate > 0.05:
                workers = max(1, workers // 2)
                delay   = round(delay + 1.0, 2)
                logger.info("AIMD ↓ throttle=%.0f%% → workers=%d delay=%.2fs", throttle_rate * 100, workers, delay)
            elif throttled_count == 0:
                workers = min(settings.BATCH_MAX_WORKERS, workers + 1)
                delay   = round(max(0.0, delay - 0.5), 2)
                logger.info("AIMD ↑ throttle=0%% → workers=%d delay=%.2fs", workers, delay)

            retries = max(0, retries - 1)
            pending = next_pending

            if pending:
                Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
                failed_path.write_text(
                    _json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                logger.warning("batch passe %d/%d: %d registros pendentes → %s",
                               pass_num + 1, max_passes, len(pending), failed_path.name)

        for row_data in pending:
            logger.error("[%s] esgotou %d passes — ThrottlingException persistente", row_data["rec_id"], max_passes)
            all_results.append({
                "id": row_data["rec_id"], "canal": row_data["canal"],
                "texto_original": mask_profanity(row_data["texto"]),
                "category": "Erro", "product": "—", "sentiment": "—", "urgency": "—",
                "summary": f"[falha após {max_passes} passes — ThrottlingException persistente]",
                "risk_level": "—", "risk_justification": "",
            })

        if failed_path.exists() and not pending:
            failed_path.unlink()

        finished_at = now_brt().strftime("%Y-%m-%d %H:%M:%S (UTC-3)")
        elapsed_s   = time.time() - t_start
        paths = write_outputs(
            all_results, stem=stem,
            started_at=started_at, finished_at=finished_at, elapsed_s=elapsed_s,
            pass_stats=pass_stats, label=label or None, filename=csv_name,
        )
        return Path(paths["html"]).name

    html_name = await asyncio.to_thread(_run_batch)
    stem = html_name.removesuffix(".html")
    return RedirectResponse(url=f"/report/{stem}", status_code=303)


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
    json_files = sorted(
        [f for f in out_dir.glob("report_*.json") if not f.name.endswith(".meta.json")],
        reverse=True,
    )

    def _read_meta(stem: str) -> dict:
        meta = out_dir / f"{stem}.meta.json"
        if meta.exists():
            try:
                return _json.loads(meta.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _report_entry(f: Path) -> dict:
        meta = _read_meta(f.stem)
        return {
            "stem":       f.stem,
            "ts_display": f.stem,
            "size_kb":    round(f.stat().st_size / 1024, 1),
            "has_json":   True,
            "has_csv":    (out_dir / f"{f.stem}.csv").exists(),
            "has_md":     (out_dir / f"{f.stem}.md").exists(),
            "label":      meta.get("label", ""),
            "filename":   meta.get("filename", ""),
        }

    reports = [_report_entry(f) for f in json_files]
    return templates.TemplateResponse("reports.html.j2", {
        "request": request,
        "reports": reports,
        "total":   len(json_files),
    })


@app.get("/report/{stem}", response_class=HTMLResponse)
def report_detail(request: Request, stem: str):
    out_dir   = Path(settings.OUTPUT_DIR)
    json_path = out_dir / f"{stem}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    results = _json.loads(json_path.read_text(encoding="utf-8"))
    meta_path = out_dir / f"{stem}.meta.json"
    meta = _json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    ctx = build_report_context(results, meta)
    return templates.TemplateResponse("report.html.j2", {"request": request, "stem": stem, **ctx})


# ── Rotas: traces / log ───────────────────────────────────────────────────────

@app.get("/traces", response_class=HTMLResponse)
def traces_page(request: Request):
    data = get_traces()

    series: dict[str, list[float]] = {"total_ms": [], "triage": [], "risk": [], "report": []}
    for t in data:
        tm = t.get("timings_ms", {})
        series["total_ms"].append(float(t.get("total_ms") or 0))
        if not t.get("blocked"):
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
        pipeline = t_ms + r_ms + rp_ms
        total_e2e = int(t.get("total_ms") or gi_ms + pipeline)
        traces_display.append({
            **t,
            "t_ms":            t_ms,
            "r_ms":            r_ms,
            "rp_ms":           rp_ms,
            "gi_ms":           gi_ms,
            "total_display":   total_e2e,
            "bar_triage":      bar_width_px(t_ms,  pipeline),
            "bar_risk":        bar_width_px(r_ms,  pipeline),
            "bar_report":      bar_width_px(rp_ms, pipeline),
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


@app.post("/traces/recompose")
def traces_recompose(stem: str) -> JSONResponse:
    """Reconstrói o log de execução em memória a partir de um relatório batch salvo."""
    json_path = Path(settings.OUTPUT_DIR) / f"{stem}.json"
    if not json_path.exists():
        raise HTTPException(404, f"Relatório '{stem}' não encontrado")

    items = _json.loads(json_path.read_text(encoding="utf-8"))
    for item in reversed(items):
        texto = item.get("texto_original", "")
        tm    = item.get("timings_ms", {})
        inject_trace({
            "trace_id":     item.get("id", "?"),
            "timestamp":    item.get("timestamp", stem),
            "text_preview": (texto[:70] + "…") if len(texto) > 70 else texto,
            "blocked":      item.get("blocked", False),
            "category":     item.get("category"),
            "urgency":      item.get("urgency"),
            "risk_level":   item.get("risk_level"),
            "timings_ms":   tm,
            "total_ms": sum_timings(tm),
        })

    return JSONResponse({"status": "ok", "recomposed": len(items)})


# ── Rotas: API de registros ───────────────────────────────────────────────────

@app.get("/api/record/{record_id}")
def get_record(record_id: str) -> JSONResponse:
    """Busca o payload completo de um registro pelo ID nos relatórios JSON salvos."""
    out_dir = Path(settings.OUTPUT_DIR)
    for json_file in sorted(out_dir.glob("*.json"), reverse=True):
        try:
            items = _json.loads(json_file.read_text(encoding="utf-8"))
            if isinstance(items, list):
                for item in items:
                    if item.get("id") == record_id:
                        return JSONResponse(item)
        except Exception:
            continue
    raise HTTPException(404, f"Registro '{record_id}' não encontrado nos relatórios salvos")


# ── Rotas: documentação ───────────────────────────────────────────────────────

@app.get("/adr", response_class=HTMLResponse)
def adr_page():
    if _ADR_PATH.exists():
        return HTMLResponse(_ADR_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<p>ADR não encontrado em assets/adr.html</p>", status_code=404)
