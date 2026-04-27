
import csv
import io
import logging
import math
import statistics
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .graph import analyze, clear_traces, get_traces
from .profanity import mask as mask_profanity
from .rag.ingest import ingest_all
from .rag.retriever import _store as _rag_store
from .report_writer import write_outputs
from .settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")


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


app = FastAPI(title="FinGuard - Nível 3 (Arquiteto da Solução)", version="0.1.0", lifespan=lifespan)

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.filters["tojson"] = lambda v, indent=None: __import__("json").dumps(
    v, ensure_ascii=False, indent=indent
)
app.mount("/output", StaticFiles(directory=settings.OUTPUT_DIR, check_dir=False), name="output")

_ADR_PATH = BASE.parent.parent / "assets" / "adr.html"


@app.get("/adr", response_class=HTMLResponse)
def adr_page():
    if _ADR_PATH.exists():
        return HTMLResponse(_ADR_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<p>ADR não encontrado em assets/adr.html</p>", status_code=404)


class AnalyzeRequest(BaseModel):
    text: str
    product_hint: str | None = None


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html.j2", {"request": request})


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


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


# ─── Admin ────────────────────────────────────────────────────────────────────

def _count_output_files() -> int:
    return len([f for f in Path(settings.OUTPUT_DIR).glob("*") if f.is_file()])


def _rag_vector_count() -> int:
    try:
        return _rag_store().total_vectors
    except Exception:
        return -1


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    n_out = _count_output_files()
    n_vec = _rag_vector_count()
    n_traces = len(get_traces())
    docs = [d.name for d in Path(settings.RAG_DOCS_DIR).iterdir() if d.is_file()]
    guardrail_id = settings.GUARDRAIL_ID or None
    guardrail_ver = settings.GUARDRAIL_VERSION if guardrail_id else "—"

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Admin — FinGuard</title>
<style>
  body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         max-width:700px; margin:40px auto; padding:0 16px; color:#1f2937; background:#f9fafb; }}
  h1 {{ margin-bottom:4px; }}
  .muted {{ color:#6b7280; font-size:13px; }}
  .card {{ background:white; padding:20px; border-radius:8px;
           box-shadow:0 1px 3px rgba(0,0,0,.08); margin-top:16px; }}
  .stat-row {{ display:flex; justify-content:space-between; align-items:center;
               padding:10px 0; border-bottom:1px solid #e5e7eb; font-size:14px; }}
  .stat-row:last-child {{ border-bottom:none; }}
  .stat-val {{ font-weight:700; font-size:18px; }}
  .stat-val.zero {{ color:#9ca3af; }}
  .stat-val.ok {{ color:#059669; }}
  .stat-val.warn {{ color:#d97706; }}
  .btn {{ display:inline-block; padding:9px 18px; border-radius:6px; font-size:13px;
          font-weight:500; border:none; cursor:pointer; text-decoration:none; }}
  .btn-danger {{ background:#dc2626; color:white; }}
  .btn-danger:hover {{ background:#b91c1c; }}
  .btn-primary {{ background:#2563eb; color:white; }}
  .btn-primary:hover {{ background:#1d4ed8; }}
  .btn-gray {{ background:#6b7280; color:white; }}
  .btn-gray:hover {{ background:#4b5563; }}
  .actions {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }}
  #result {{ margin-top:12px; padding:12px; border-radius:6px; font-size:13px;
             font-family:monospace; white-space:pre; display:none; }}
  #result.ok   {{ background:#d1fae5; color:#065f46; }}
  #result.err  {{ background:#fee2e2; color:#991b1b; }}
  .doc-list {{ font-size:13px; color:#374151; margin:8px 0 0; padding-left:20px; }}
</style>
</head>
<body>
<nav style="display:flex;gap:12px;font-size:13px;margin-bottom:16px">
  <a href="/" style="color:#2563eb;text-decoration:none">← Voltar</a>
  <a href="/reports" style="color:#2563eb;text-decoration:none">Relatórios</a>
  <a href="/traces" style="color:#2563eb;text-decoration:none">Log</a>
  <a href="/adr" style="color:#2563eb;text-decoration:none">ADR</a>
</nav>
<h1 style="margin-top:4px">Painel Administrativo</h1>
<p class="muted">Gerenciamento de estado do FinGuard. Use antes ou após apresentações.</p>

<div class="card">
  <h3 style="margin-top:0">Estado atual</h3>

  <div class="stat-row">
    <div>
      <strong>Relatórios gerados</strong>
      <div class="muted">Arquivos em /output (JSON, CSV, MD, HTML)</div>
    </div>
    <span class="stat-val {'ok' if n_out > 0 else 'zero'}">{n_out}</span>
  </div>

  <div class="stat-row">
    <div>
      <strong>Índice RAG — vetores</strong>
      <div class="muted">Chunks da Política Interna indexados no FAISS</div>
      <ul class="doc-list">{''.join(f'<li>{d}</li>' for d in docs)}</ul>
    </div>
    <span class="stat-val {'ok' if n_vec > 0 else 'warn'}">{n_vec if n_vec >= 0 else 'erro'}</span>
  </div>

  <div class="stat-row">
    <div>
      <strong>Log de execuções (memória)</strong>
      <div class="muted">Traces em memória desde o último restart</div>
    </div>
    <span class="stat-val {'ok' if n_traces > 0 else 'zero'}">{n_traces}</span>
  </div>

  <div class="stat-row">
    <div>
      <strong>Bedrock Guardrail (Nível 3)</strong>
      <div class="muted">ID: <code>{guardrail_id or 'não configurado'}</code> · Versão: {guardrail_ver}</div>
    </div>
    <span class="stat-val {'ok' if guardrail_id else 'warn'}"
          title="{'Ativo' if guardrail_id else 'Defina GUARDRAIL_ID no ambiente'}">
      {'✓ Ativo' if guardrail_id else '⚠ Fallback local'}
    </span>
  </div>
</div>

<div class="card">
  <h3 style="margin-top:0">Ações</h3>

  <div class="actions">
    <button class="btn btn-primary" onclick="doIngest()">↺ Re-ingerir documentos</button>
    <button class="btn btn-gray"    onclick="doReset('traces')">Limpar log de execuções</button>
    <button class="btn btn-gray"    onclick="doReset('outputs')">Limpar relatórios</button>
    <button class="btn btn-gray"    onclick="doReset('index')">Zerar índice RAG</button>
    <button class="btn btn-danger"  onclick="doReset('all')"
            style="margin-left:auto">⚠ Zerar tudo</button>
  </div>
  <div id="result"></div>
</div>

<script>
async function doIngest() {{
  setResult('Iniciando ingestão…', '');
  const r = await fetch('/ingest', {{method:'POST'}});
  const d = await r.json();
  if (r.status === 409) {{ setResult(JSON.stringify(d, null, 2), 'err'); return; }}
  setResult('⏳ Ingestão em andamento — embedando chunks via Bedrock Titan…', '');
  const poll = setInterval(async () => {{
    const s = await fetch('/ingest/status');
    const st = await s.json();
    if (st.status === 'done') {{
      clearInterval(poll);
      setResult(JSON.stringify(st, null, 2), 'ok');
      setTimeout(() => location.reload(), 1500);
    }} else if (st.status === 'error') {{
      clearInterval(poll);
      setResult(JSON.stringify(st, null, 2), 'err');
    }} else {{
      setResult('⏳ Ingestão em andamento… ' + new Date().toLocaleTimeString(), '');
    }}
  }}, 2000);
}}

async function doReset(target) {{
  const labels = {{
    traces:  'o log de execuções em memória',
    outputs: 'todos os relatórios gerados',
    index:   'o índice RAG (será necessário re-ingerir)',
    all:     'TUDO (relatórios, índice RAG e log de execuções)',
  }};
  if (!confirm('Confirma: zerar ' + labels[target] + '?')) return;
  setResult('Zerando…', '');
  const r = await fetch('/admin/reset?target=' + target, {{method:'POST'}});
  const d = await r.json();
  setResult(JSON.stringify(d, null, 2), r.ok ? 'ok' : 'err');
  if (r.ok) setTimeout(() => location.reload(), 1500);
}}

function setResult(text, cls) {{
  const el = document.getElementById('result');
  el.textContent = text;
  el.className = cls;
  el.style.display = 'block';
}}
</script>
</body>
</html>""")


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


@app.get("/reports", response_class=HTMLResponse)
def reports_page():
    """Lista todos os relatórios gerados em /output, agrupados por execução de batch."""
    out_dir = Path(settings.OUTPUT_DIR)
    html_files = sorted(out_dir.glob("*.html"), reverse=True)

    rows = ""
    for html_file in html_files:
        stem = html_file.stem
        ts_display = stem  # formato já é YYYY-MM-DD-HH-MM-SS ou nome legível
        size_kb = round(html_file.stat().st_size / 1024, 1)
        has = {ext: (out_dir / f"{stem}.{ext}").exists() for ext in ("json", "csv", "md")}

        def dl(ext, color):
            if not has[ext]:
                return f'<span style="color:#d1d5db">— {ext.upper()}</span>'
            return (f'<a href="/output/{stem}.{ext}" download '
                    f'style="color:white;background:{color};padding:3px 10px;'
                    f'border-radius:4px;font-size:12px;text-decoration:none">'
                    f'⬇ {ext.upper()}</a>')

        rows += f"""<tr>
          <td style="font-size:13px;font-family:monospace">{ts_display}</td>
          <td style="font-size:12px;color:#6b7280">{size_kb} KB</td>
          <td>
            <a href="/output/{stem}.html"
               style="color:white;background:#1e40af;padding:3px 10px;
                      border-radius:4px;font-size:12px;text-decoration:none">
              &#128196; Ver relatório
            </a>
          </td>
          <td style="display:flex;gap:6px;flex-wrap:wrap">
            {dl('json','#1e40af')} {dl('csv','#047857')} {dl('md','#6b7280')}
          </td>
        </tr>"""

    empty = "<tr><td colspan='4' style='text-align:center;padding:32px;color:#9ca3af'>Nenhum relatório gerado ainda. Processe um CSV para começar.</td></tr>"

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Relatórios — FinGuard</title>
<style>
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         max-width:900px; margin:32px auto; padding:0 16px; color:#1f2937; background:#f9fafb; }}
  h1 {{ margin-bottom:4px; }}
  .muted {{ color:#6b7280; font-size:13px; margin-bottom:16px; display:block; }}
  table {{ width:100%; border-collapse:collapse; background:white; border-radius:8px;
           overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  th {{ background:#1e40af; color:white; padding:10px 14px; text-align:left;
        font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
  td {{ padding:10px 14px; border-bottom:1px solid #e5e7eb; vertical-align:middle; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:#f0f9ff; }}
  a {{ color:#2563eb; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  nav {{ display:flex; gap:12px; font-size:13px; margin-bottom:16px; }}
</style>
</head>
<body>
<nav>
  <a href="/">← Voltar</a>
  <a href="/traces">Log de execuções</a>
  <a href="/admin" style="color:#6b7280">Admin</a>
</nav>
<h1>Relatórios gerados</h1>
<span class="muted">{len(html_files)} relatório(s) em /output — ordenados do mais recente para o mais antigo.</span>
<table>
  <thead>
    <tr>
      <th>Timestamp</th>
      <th>Tamanho</th>
      <th>Relatório</th>
      <th>Downloads</th>
    </tr>
  </thead>
  <tbody>{rows if html_files else empty}</tbody>
</table>
</body>
</html>""")


@app.get("/traces", response_class=HTMLResponse)
def traces_page():
    """Exibe log em memória das últimas análises com estatísticas de latência."""
    data = get_traces()

    def _pill(value: str | None, mapping: dict) -> str:
        v = (value or "").lower()
        for prefix, style in mapping.items():
            if v.startswith(prefix):
                return f'<span style="{style}">{value}</span>'
        return value or "—"

    risk_style = {
        "crít": "color:#991b1b;font-weight:600", "alt": "color:#9a3412;font-weight:600",
        "méd":  "color:#92400e", "med": "color:#92400e", "baix": "color:#065f46",
    }
    urg_style = {
        "crít": "color:#991b1b;font-weight:600", "alt": "color:#9a3412;font-weight:600",
        "méd":  "color:#92400e", "med": "color:#92400e", "baix": "color:#065f46",
    }

    # ── Estatísticas ─────────────────────────────────────────────────────────
    def _percentile(vals: list[float], p: float) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        return s[max(0, math.ceil(p * len(s)) - 1)]

    def _stats(vals: list[float]) -> dict:
        if not vals:
            return {"mean": 0, "median": 0, "stdev": 0, "p95": 0, "p99": 0}
        return {
            "mean":   round(statistics.mean(vals)),
            "median": round(statistics.median(vals)),
            "stdev":  round(statistics.stdev(vals) if len(vals) > 1 else 0),
            "p95":    round(_percentile(vals, 0.95)),
            "p99":    round(_percentile(vals, 0.99)),
        }

    keys = ("total_ms", "triage", "risk", "report")
    series: dict[str, list[float]] = {k: [] for k in keys}
    for t in data:
        tm = t.get("timings_ms", {})
        series["total_ms"].append(float(t.get("total_ms") or 0))
        series["triage"].append(float(tm.get("triage") or 0))
        series["risk"].append(float(tm.get("risk") or 0))
        series["report"].append(float(tm.get("report") or 0))

    st = {k: _stats(v) for k, v in series.items()}

    def stat_card(label: str, color: str, key: str) -> str:
        s = st[key]
        return f"""
        <div style="background:white;border-radius:8px;padding:16px;
                    box-shadow:0 1px 3px rgba(0,0,0,.08);min-width:180px;flex:1">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;
                      letter-spacing:.05em;color:{color};margin-bottom:10px">{label}</div>
          <table style="width:100%;font-size:13px;border-collapse:collapse">
            <tr><td style="color:#6b7280;padding:2px 0">Média</td>
                <td style="text-align:right;font-weight:600">{s['mean']}ms</td></tr>
            <tr><td style="color:#6b7280;padding:2px 0">Mediana</td>
                <td style="text-align:right;font-weight:600">{s['median']}ms</td></tr>
            <tr><td style="color:#6b7280;padding:2px 0">Desvio Padrão</td>
                <td style="text-align:right;font-weight:600">{s['stdev']}ms</td></tr>
            <tr style="border-top:1px solid #e5e7eb">
                <td style="color:#6b7280;padding:4px 0 2px">P95</td>
                <td style="text-align:right;font-weight:700;color:{color}">{s['p95']}ms</td></tr>
            <tr><td style="color:#6b7280;padding:2px 0">P99</td>
                <td style="text-align:right;font-weight:700;color:{color}">{s['p99']}ms</td></tr>
          </table>
        </div>"""

    stats_section = "" if not data else f"""
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px">
      {stat_card("Total (E2E)", "#1e40af", "total_ms")}
      {stat_card("① Triagem", "#4338ca", "triage")}
      {stat_card("② Risco + RAG", "#b45309", "risk")}
      {stat_card("③ Relatório", "#047857", "report")}
    </div>"""

    # ── Linhas da tabela ──────────────────────────────────────────────────────
    rows = ""
    for t in data:
        tm      = t.get("timings_ms", {})
        blocked = t.get("blocked", False)
        t_ms  = tm.get("triage", 0) or 0
        r_ms  = tm.get("risk",   0) or 0
        rp_ms = tm.get("report", 0) or 0
        gi_ms = tm.get("guardrail_input", 0) or 0
        total = t.get("total_ms", t_ms + r_ms + rp_ms)
        bar_w = lambda ms: f'{max(int(ms / max(total, 1) * 80), 1)}px'  # noqa: E731
        blocked_badge = ('<span style="background:#dc2626;color:white;font-size:10px;'
                         'padding:2px 6px;border-radius:4px;font-weight:700">BLOQUEADO</span> '
                         if blocked else "")
        timing_col = (
            f'<div style="font-size:11px;color:#dc2626">⛔ Guardrail {gi_ms}ms — pipeline não executado</div>'
            if blocked else
            f"""<div style="display:flex;flex-direction:column;gap:2px;font-size:11px">
              <div><span style="display:inline-block;width:{bar_w(t_ms)};height:8px;
                   background:#818cf8;border-radius:3px;vertical-align:middle;
                   margin-right:4px"></span>Triagem {t_ms}ms</div>
              <div><span style="display:inline-block;width:{bar_w(r_ms)};height:8px;
                   background:#fbbf24;border-radius:3px;vertical-align:middle;
                   margin-right:4px"></span>Risco {r_ms}ms</div>
              <div><span style="display:inline-block;width:{bar_w(rp_ms)};height:8px;
                   background:#34d399;border-radius:3px;vertical-align:middle;
                   margin-right:4px"></span>Relatório {rp_ms}ms</div>
            </div>"""
        )
        rows += f"""<tr{"style='background:#fff5f5'" if blocked else ""}>
          <td><code>{t['trace_id']}</code></td>
          <td>{t['timestamp']}</td>
          <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;
                     white-space:nowrap;font-size:12px">{blocked_badge}{t['text_preview']}</td>
          <td style="font-size:12px">{t.get('category') or '—'}</td>
          <td style="font-size:12px">{_pill(t.get('urgency'), urg_style)}</td>
          <td style="font-size:12px">{_pill(t.get('risk_level'), risk_style)}</td>
          <td>{timing_col}</td>
          <td style="font-weight:700;font-size:13px">{gi_ms + total}ms</td>
        </tr>"""

    empty = ("<tr><td colspan='8' style='text-align:center;padding:32px;color:#9ca3af'>"
             "Nenhuma execução ainda. Analise uma reclamação para ver o log.</td></tr>")

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Log de Execuções — FinGuard</title>
<style>
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         max-width:1100px; margin:32px auto; padding:0 16px; color:#1f2937; background:#f9fafb; }}
  h1 {{ margin-bottom:4px; }}
  .muted {{ color:#6b7280; font-size:13px; margin-bottom:16px; display:block; }}
  table {{ width:100%; border-collapse:collapse; background:white; border-radius:8px;
           overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  th {{ background:#1e40af; color:white; padding:10px 12px; text-align:left;
        font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
  td {{ padding:10px 12px; border-bottom:1px solid #e5e7eb; vertical-align:middle; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:#f0f9ff; }}
  a {{ color:#2563eb; text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  nav {{ display:flex; gap:12px; font-size:13px; margin-bottom:16px; }}
  .legend {{ display:flex; gap:16px; margin-bottom:12px; font-size:12px; color:#6b7280; }}
  .dot {{ display:inline-block; width:10px; height:10px; border-radius:2px;
          margin-right:4px; vertical-align:middle; }}
</style>
</head>
<body>
<nav>
  <a href="/">← Voltar</a>
  <a href="/reports">Relatórios</a>
  <a href="/admin" style="color:#6b7280">Admin</a>
</nav>
<h1>Log de Execuções — {len(data)} registro(s)</h1>
<span class="muted">Em memória desde o último restart. Logs completos estão no console (stdout).</span>
{stats_section}
<div class="legend">
  <span><span class="dot" style="background:#818cf8"></span>Triagem (Haiku)</span>
  <span><span class="dot" style="background:#fbbf24"></span>Risco (Sonnet + RAG)</span>
  <span><span class="dot" style="background:#34d399"></span>Relatório (consolidação)</span>
</div>
<table>
  <thead>
    <tr>
      <th>Trace ID</th><th>Hora</th><th>Texto (preview)</th>
      <th>Categoria</th><th>Urgência</th><th>Risco</th>
      <th>Tempo por Agente</th><th>Total</th>
    </tr>
  </thead>
  <tbody>{rows if data else empty}</tbody>
</table>
</body>
</html>""")


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
        canal = (row.get("canal") or "").strip() or "Não informado"
        rec_id = (row.get("id") or f"REC-{i:05d}")
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

    from datetime import datetime as _dt
    stem = _dt.utcnow().strftime("report_%Y-%m-%d-%H-%M-%S")
    paths = write_outputs(results, stem=stem)
    return RedirectResponse(url=f"/output/{Path(paths['html']).name}", status_code=303)
