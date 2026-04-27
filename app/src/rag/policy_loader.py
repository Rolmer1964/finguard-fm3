import logging
from pathlib import Path

from ..settings import settings

logger = logging.getLogger("rag")

_cache: str | None = None


def load_policy() -> str:
    """Carrega a política interna do disco e cacheia em memória."""
    global _cache
    if _cache is not None:
        return _cache
    path = Path(settings.POLICY_PATH)
    if not path.exists():
        logger.warning("Política interna não encontrada em %s", path)
        _cache = ""
    else:
        _cache = path.read_text(encoding="utf-8")
    return _cache
