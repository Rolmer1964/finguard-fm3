"""Interface de consulta ao índice. Usado pelo classificador / agentes."""

from __future__ import annotations

import logging
from functools import lru_cache

from ..settings import settings
from .embedder import embed_one
from .store import RetrievedChunk, VectorStore

logger = logging.getLogger("rag.retriever")


@lru_cache(maxsize=1)
def _store() -> VectorStore:
    s = VectorStore(dim=settings.EMBED_DIM, index_dir=settings.RAG_INDEX_DIR)
    s.load()
    return s


def retrieve(query: str, k: int | None = None) -> list[RetrievedChunk]:
    """Devolve top-k chunks mais similares ao `query` (lista vazia se índice ausente)."""
    k = k or settings.RAG_TOP_K
    store = _store()
    if store.total_vectors == 0:
        return []
    try:
        qvec = embed_one(query)
    except Exception:
        logger.exception("falha ao embedar query; retornando contexto vazio")
        return []
    return store.search(qvec, k=k)


def format_for_prompt(chunks: list[RetrievedChunk]) -> str:
    """Formata os chunks como um bloco de contexto para injetar no prompt."""
    if not chunks:
        return ""
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] Fonte: {c.source} (trecho {c.chunk_idx})\n{c.text}")
    return "Trechos relevantes da Política Interna:\n\n" + "\n\n---\n\n".join(parts)
