"""Geração do ADR (Architectural Decision Record) em HTML navegável.

O ADR é renderizado a partir de um template Jinja2, com dados de runtime
(modelos configurados, status do guardrail, contagem de docs no RAG).
Pode ser servido pelo endpoint /adr ou salvo em /app/docs/adr.html.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .settings import settings

logger = logging.getLogger("adr")

_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(["html"]),
)


def _rag_status() -> dict:
    """Lê o manifest do RAG, se existir, para mostrar volume indexado no ADR."""
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


def render_adr() -> str:
    return _env.get_template("adr.html.j2").render(
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
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


def write_adr() -> str:
    html = render_adr()
    out_dir = Path(settings.DOCS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "adr.html"
    path.write_text(html, encoding="utf-8")
    logger.info("ADR salvo em %s", path)
    return str(path)
