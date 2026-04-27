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


def _bucket(items: list[dict], key: str) -> dict[str, int]:
    return dict(Counter((it.get(key) or "Não informado") for it in items))


def write_outputs(results: list[dict], stem: str | None = None) -> dict[str, str]:
    """Grava JSON, CSV e HTML com os resultados de uma execução em batch.

    `results` é uma lista de dicts contendo: id, texto_original, categoria,
    produto, sentimento, urgencia, resumo.

    Retorna paths gerados.
    """
    out_dir = Path(settings.OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = stem or f"resultado-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"
    html_path = out_dir / f"{stem}.html"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = ["id", "texto_original", "categoria", "produto", "sentimento", "urgencia", "resumo"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k, "") for k in fields})

    html = _env.get_template("report.html.j2").render(
        results=results,
        total=len(results),
        by_category=_bucket(results, "categoria"),
        by_product=_bucket(results, "produto"),
        by_urgency=_bucket(results, "urgencia"),
        by_sentiment=_bucket(results, "sentimento"),
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )
    html_path.write_text(html, encoding="utf-8")

    return {"json": str(json_path), "csv": str(csv_path), "html": str(html_path)}
