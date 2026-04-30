"""Geração do Relatório Técnico de Entrega em HTML navegável.

Renderizado a partir de um template Jinja2, com dados de runtime
(modelos configurados, status do guardrail, contagem de docs no RAG).
Servido pelo endpoint /relatorio-tecnico ou salvo em /app/docs/relatorio-tecnico.html.
"""

from __future__ import annotations

import json
import logging
from .settings import now_brt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .settings import settings

logger = logging.getLogger("relatorio_tecnico")

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]),
)


def _rag_status() -> dict:
    """Lê o manifest do RAG, se existir, para mostrar volume indexado no relatório."""
    mpath = Path(settings.RAG_INDEX_DIR) / "manifest.json"
    if not mpath.exists():
        return {"available": False}
    try:
        m = json.loads(mpath.read_text(encoding="utf-8"))
        return {
            "available": True,
            "vectors": m.get("next_id", 0),
            "files": [
                {"path": p, "chunks": len(v.get("chunk_ids", [])), "hash": v.get("hash", "")[:8]}
                for p, v in m.get("files", {}).items()
            ],
            "updated_at": m.get("updated_at"),
        }
    except Exception as exc:
        logger.warning("falha lendo manifest do RAG: %s", exc)
        return {"available": False}


def render_relatorio() -> str:
    return _env.get_template("relatorio_tecnico.html.j2").render(
        generated_at=now_brt().isoformat(timespec="seconds"),
        models={
            "triage": settings.BEDROCK_MODEL_TRIAGE,
            "risk": settings.BEDROCK_MODEL_RISK,
            "embed": settings.BEDROCK_EMBED_MODEL_ID,
        },
        guardrail={
            "configured": bool(settings.BEDROCK_GUARDRAIL_ID),
            "id_short": (settings.BEDROCK_GUARDRAIL_ID[:8] + "…") if settings.BEDROCK_GUARDRAIL_ID else None,
            "version": settings.BEDROCK_GUARDRAIL_VERSION,
        },
        rag=_rag_status(),
    )


def write_relatorio() -> str:
    html = render_relatorio()
    out_dir = Path(settings.DOCS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "relatorio-tecnico.html"
    path.write_text(html, encoding="utf-8")
    logger.info("Relatório Técnico de Entrega salvo em %s", path)
    return str(path)
