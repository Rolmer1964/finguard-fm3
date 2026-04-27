"""Cliente de embeddings via Bedrock Titan Text Embeddings v2.

Modelo: amazon.titan-embed-text-v2:0
- Aceita até ~8K tokens de entrada
- Retorna vetor de 1024 dim (configurável: 256/512/1024) normalizado
- Custo (us-east-1): ~$0.00002 / 1k input tokens
"""

from __future__ import annotations

import json
import logging
import time

import boto3
import numpy as np

from ..settings import settings

logger = logging.getLogger("rag.embedder")


def _client():
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        aws_session_token=settings.AWS_SESSION_TOKEN or None,
    )


def embed_one(text: str) -> np.ndarray:
    body = {
        "inputText": text,
        "dimensions": settings.EMBED_DIM,
        "normalize": True,
    }
    resp = _client().invoke_model(
        modelId=settings.BEDROCK_EMBED_MODEL_ID,
        accept="application/json",
        contentType="application/json",
        body=json.dumps(body),
    )
    payload = json.loads(resp["body"].read())
    vec = np.array(payload["embedding"], dtype="float32")
    return vec


def embed_batch(texts: list[str], *, log_every: int = 25) -> np.ndarray:
    """Embeda uma lista. Bedrock Titan não tem endpoint batch; iteramos serial.

    Para volumes grandes, paralelizar com ThreadPoolExecutor é seguro (Bedrock é
    rate-limited mas tolera concorrência moderada).
    """
    out = np.zeros((len(texts), settings.EMBED_DIM), dtype="float32")
    t0 = time.time()
    for i, t in enumerate(texts):
        out[i] = embed_one(t)
        if (i + 1) % log_every == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(texts) - i - 1) / rate if rate > 0 else 0
            logger.info("embed %d/%d (%.1f/s, ETA %.0fs)", i + 1, len(texts), rate, eta)
    logger.info("embed concluído: %d vetores em %.1fs", len(texts), time.time() - t0)
    return out
