from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .settings import settings

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]),
)


def render_report(dashboard: dict) -> str:
    tpl = _env.get_template("report.html.j2")
    return tpl.render(
        d=dashboard,
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )


def write_report(dashboard: dict) -> str:
    html = render_report(dashboard)
    out_dir = Path(settings.REPORTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"report-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.html"
    path = out_dir / fname
    path.write_text(html, encoding="utf-8")
    return str(path)
