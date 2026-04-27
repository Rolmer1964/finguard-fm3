"""CLI para rodar a ingestão RAG localmente.

Uso (recomendado, dentro do container que já tem deps + creds AWS):
    docker compose exec app python -m src.rag.ingest

Ou via Makefile:
    make rag-ingest

Este script é só um wrapper fino para chamar de fora do container caso
você prefira (precisa do mesmo .env carregado e das deps Python instaladas
localmente — boto3, faiss-cpu, pypdf, numpy).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

# Aponta para os caminhos locais (fora do container)
os.environ.setdefault("RAG_DOCS_DIR", str(ROOT / "assets" / "docs"))
os.environ.setdefault("RAG_INDEX_DIR", str(ROOT / "assets" / "index"))

from src.rag.ingest import main  # noqa: E402

if __name__ == "__main__":
    main()
