from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .settings import settings

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]),
)


def render_adr(dashboard: dict | None = None) -> str:
    tpl = _env.get_template("adr.html.j2")
    return tpl.render(
        d=dashboard or {},
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        models={
            "triage": settings.BEDROCK_MODEL_TRIAGE,
            "risk": settings.BEDROCK_MODEL_RISK,
            "report": settings.BEDROCK_MODEL_REPORT,
        },
    )


def write_adr(dashboard: dict | None = None) -> str:
    html = render_adr(dashboard)
    out_dir = Path(settings.DOCS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "adr.html"
    path.write_text(html, encoding="utf-8")
    return str(path)
