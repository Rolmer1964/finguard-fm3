"""Lê o CSV sintético e envia tudo via /api/complaints/bulk autenticado.

Uso:
    python scripts/seed_complaints.py [csv_path=data/synthetic_complaints.csv]

Variáveis:
    FINGUARD_URL    URL do gateway (default: http://localhost:8000)
    ADMIN_EMAIL     e-mail do admin (do .env)
    ADMIN_PASSWORD  senha do admin (do .env)
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import urllib.request
import urllib.error
import json


def _post(url: str, payload: dict, token: str | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise SystemExit(f"HTTP {e.code} em {url}: {body}") from e


def _load_env() -> dict:
    env: dict[str, str] = {}
    p = Path(".env")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def main(csv_path: str = "data/synthetic_complaints.csv") -> None:
    env = _load_env()
    base = os.environ.get("FINGUARD_URL", "http://localhost:8000")
    email = os.environ.get("ADMIN_EMAIL") or env.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD") or env.get("ADMIN_PASSWORD")
    if not email or not password:
        raise SystemExit("ADMIN_EMAIL/ADMIN_PASSWORD não definidos (.env ou variáveis de ambiente).")

    print(f"Login em {base} como {email}...")
    auth = _post(f"{base}/api/auth/login", {"email": email, "password": password})
    token = auth["access_token"]

    p = Path(csv_path)
    if not p.exists():
        raise SystemExit(f"CSV não encontrado: {p}. Rode `make generate-data` antes.")

    items = []
    with p.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append({
                "text": row["texto_reclamacao"],
                "channel": row["canal"],
                "product_hint": row["produto"] or None,
                "external_id": row["id"],
            })

    print(f"Enviando {len(items)} reclamações em lote ao {base}/api/complaints/bulk (pode demorar alguns minutos)...")
    result = _post(f"{base}/api/complaints/bulk", {"items": items}, token=token)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/synthetic_complaints.csv"
    main(csv_path)
