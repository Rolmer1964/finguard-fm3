"""Ingestão incremental: detecta novos/alterados/removidos e atualiza o índice.

Uso programático:
    from src.rag.ingest import ingest_all
    stats = ingest_all()
    print(stats)

Uso via CLI:
    python -m src.rag.ingest
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..settings import settings
from .chunker import chunk_text
from .embedder import embed_batch
from .loader import load_documents
from .store import VectorStore

logger = logging.getLogger("rag.ingest")


@dataclass
class IngestStats:
    new: list[str]
    changed: list[str]
    removed: list[str]
    skipped: list[str]
    chunks_added: int
    chunks_removed: int
    total_vectors_after: int

    def as_dict(self) -> dict:
        return {
            "new": self.new, "changed": self.changed, "removed": self.removed,
            "skipped": self.skipped, "chunks_added": self.chunks_added,
            "chunks_removed": self.chunks_removed,
            "total_vectors_after": self.total_vectors_after,
        }


def ingest_all() -> IngestStats:
    """Sincroniza o índice com o estado atual de RAG_DOCS_DIR."""
    store = VectorStore(dim=settings.EMBED_DIM, index_dir=settings.RAG_INDEX_DIR)
    store.load()

    docs = load_documents(settings.RAG_DOCS_DIR)
    on_disk = {d.relpath: d for d in docs}
    known = store.known_files()

    new_paths = sorted(set(on_disk) - known)
    removed_paths = sorted(known - set(on_disk))
    changed_paths = sorted(p for p in (set(on_disk) & known) if store.file_hash(p) != on_disk[p].sha256)
    skipped_paths = sorted(p for p in (set(on_disk) & known) if store.file_hash(p) == on_disk[p].sha256)

    chunks_removed = 0
    for p in removed_paths + changed_paths:
        before = store.total_vectors
        store.remove_file(p)
        chunks_removed += before - store.total_vectors

    chunks_added = 0
    for p in new_paths + changed_paths:
        doc = on_disk[p]
        chunks = chunk_text(doc.text, max_chars=settings.RAG_CHUNK_CHARS, overlap=settings.RAG_CHUNK_OVERLAP)
        if not chunks:
            logger.warning("nenhum chunk gerado para %s; pulando", p)
            continue
        logger.info("embedando %d chunks de %s", len(chunks), p)
        vectors = embed_batch(chunks)
        store.add_file(p, doc.sha256, chunks, vectors)
        chunks_added += len(chunks)

    store.save()
    stats = IngestStats(
        new=new_paths, changed=changed_paths, removed=removed_paths, skipped=skipped_paths,
        chunks_added=chunks_added, chunks_removed=chunks_removed,
        total_vectors_after=store.total_vectors,
    )
    logger.info("ingestão concluída: %s", stats.as_dict())
    return stats


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stats = ingest_all()
    import json
    print(json.dumps(stats.as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
