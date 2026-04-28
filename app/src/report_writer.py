import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .settings import settings

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]),
)
_env.filters["tojson"] = lambda v, indent=None: json.dumps(v, ensure_ascii=False, indent=indent)


def _fmt_elapsed(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    m, s = divmod(int(seconds), 60)
    return f"{m}min {s:02d}s" if m else f"{s}s"


def _bucket(items: list[dict], key: str) -> dict[str, int]:
    return dict(Counter((it.get(key) or "Não informado") for it in items))


def _build_recommendations(by_category: dict, by_risk: dict, critical: list) -> list[str]:
    recs: list[str] = []
    if critical:
        recs.append(f"Escalar imediatamente {len(critical)} reclamação(ões) crítica(s) para Compliance.")
    top_cat = max(by_category.items(), key=lambda x: x[1], default=(None, 0))
    if top_cat[0] and top_cat[1] >= 3:
        recs.append(f"Categoria predominante: {top_cat[0]} ({top_cat[1]} casos). Avaliar causa-raiz.")
    high_or_crit = by_risk.get("Alto", 0) + by_risk.get("Crítico", 0)
    if high_or_crit >= 5:
        recs.append("Volume relevante de risco Alto/Crítico — considerar reforço da Ouvidoria.")
    if not recs:
        recs.append("Nenhuma ação prioritária identificada no período analisado.")
    return recs


def _render_md(items: list[dict], totals: dict, critical: list, recs: list[str]) -> str:
    lines = [
        "# FinGuard — Relatório Gerencial (Nível 3)",
        "",
        f"_Gerado em {datetime.utcnow().isoformat(timespec='seconds')}Z_",
        "",
        "## Resumo",
        f"- Total de reclamações: **{len(items)}**",
        f"- Críticas (urgência ou risco): **{len(critical)}**",
        "",
        "## Distribuições",
        "",
        "### Por categoria",
    ]
    for k, v in sorted(totals["by_category"].items(), key=lambda x: -x[1]):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Por nível de risco")
    for k, v in sorted(totals["by_risk"].items(), key=lambda x: -x[1]):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Reclamações críticas")
    if not critical:
        lines.append("_Nenhuma reclamação crítica no período._")
    else:
        for c in critical:
            lines.append(f"- **{c['id']}** · {c.get('category')} · {c.get('product')} · risco **{c.get('risk_level')}** — {c.get('summary')}")
    lines.append("")
    lines.append("## Recomendações")
    for r in recs:
        lines.append(f"- {r}")
    return "\n".join(lines)


def build_report_context(results: list[dict], meta: dict | None = None) -> dict:
    """Computa todas as variáveis de contexto do template a partir de results + meta."""
    meta = meta or {}
    unblocked = [r for r in results if r.get("category") != "Bloqueado"]
    by_category = _bucket(results, "category")
    by_product = _bucket(unblocked, "product")
    by_urgency = _bucket(unblocked, "urgency")
    by_risk = _bucket(unblocked, "risk_level")
    by_sentiment = _bucket(unblocked, "sentiment")
    by_canal = _bucket(results, "canal")
    critical = [r for r in results if r.get("urgency") == "Crítica" or r.get("risk_level") == "Crítico"]
    totals = {
        "by_category": by_category, "by_product": by_product,
        "by_urgency": by_urgency, "by_risk": by_risk,
        "by_sentiment": by_sentiment, "by_canal": by_canal,
    }
    recs = _build_recommendations(by_category, by_risk, critical)
    elapsed_s = meta.get("elapsed_s")
    return {
        "results": results,
        "total": len(results),
        "critical": critical,
        "by_category": by_category,
        "by_product": by_product,
        "by_urgency": by_urgency,
        "by_risk": by_risk,
        "by_sentiment": by_sentiment,
        "by_canal": by_canal,
        "recommendations": recs,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "started_at": meta.get("started_at", "—"),
        "finished_at": meta.get("finished_at", "—"),
        "elapsed_s": elapsed_s,
        "elapsed_fmt": _fmt_elapsed(elapsed_s),
        "pass_stats": meta.get("pass_stats") or [],
    }


def write_outputs(
    results: list[dict],
    stem: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    elapsed_s: float | None = None,
    pass_stats: list[dict] | None = None,
    label: str | None = None,
    filename: str | None = None,
) -> dict[str, str]:
    """Grava JSON, CSV, MD e HTML com os resultados de uma execução em batch."""
    out_dir = Path(settings.OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = stem or f"relatorio-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    meta: dict = {}
    if label:
        meta["label"] = label
    if filename:
        meta["filename"] = filename
    if started_at:
        meta["started_at"] = started_at
    if finished_at:
        meta["finished_at"] = finished_at
    if elapsed_s is not None:
        meta["elapsed_s"] = elapsed_s
    if pass_stats:
        meta["pass_stats"] = pass_stats
    if meta:
        (out_dir / f"{stem}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"
    md_path = out_dir / f"{stem}.md"
    html_path = out_dir / f"{stem}.html"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = ["id", "canal", "texto_original", "category", "product", "sentiment", "urgency",
              "summary", "risk_level", "risk_justification"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in fields})

    ctx = build_report_context(results, meta)
    totals = {k: ctx[k] for k in ("by_category", "by_product", "by_urgency", "by_risk", "by_sentiment", "by_canal")}

    md_path.write_text(_render_md(results, totals, ctx["critical"], ctx["recommendations"]), encoding="utf-8")

    html = _env.get_template("report.html.j2").render(stem=stem, **ctx)
    html_path.write_text(html, encoding="utf-8")

    return {"json": str(json_path), "csv": str(csv_path), "md": str(md_path), "html": str(html_path)}
