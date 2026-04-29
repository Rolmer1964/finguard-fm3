from datetime import datetime, timedelta, timezone

from pydantic_settings import BaseSettings, SettingsConfigDict

TZ_BRT = timezone(timedelta(hours=-3))


def now_brt() -> datetime:
    return datetime.now(TZ_BRT)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_SESSION_TOKEN: str | None = None

    # Combinação estratégica: barato para classificação, melhor para risco.
    BEDROCK_MODEL_TRIAGE: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    BEDROCK_MODEL_RISK: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    # Embeddings para o RAG (Titan v2: 1024 dim, normalizado)
    BEDROCK_EMBED_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    EMBED_DIM: int = 1024

    OUTPUT_DIR: str = "/app/output"

    # ---- Bedrock Guardrails (Nível 3) ----
    GUARDRAIL_ID: str | None = None           # guardrail de entrada (injection, ameaças)
    GUARDRAIL_VERSION: str = "DRAFT"
    GUARDRAIL_ID_OUTPUT: str | None = None    # guardrail de saída (PII + tom)
    GUARDRAIL_VERSION_OUTPUT: str = "DRAFT"

    # ---- Batch paralelo ----
    BATCH_MAX_WORKERS: int = 5
    BATCH_RATE_LIMIT_DELAY: float = 0.0
    BATCH_MAX_RETRIES: int = 2
    # Passes de recuperação para registros com ThrottlingException
    BATCH_MAX_PASSES: int = 3
    BATCH_RETRY_WORKERS: int = 2
    BATCH_RETRY_DELAY: float = 15.0  # segundos de espera entre passes

    # ---- RAG (alimenta o agente de risco com trechos da Política Interna) ----
    RAG_DOCS_DIR: str = "/app/assets/docs"
    RAG_INDEX_DIR: str = "/app/assets/index"
    RAG_TOP_K: int = 4
    RAG_CHUNK_CHARS: int = 1000
    RAG_CHUNK_OVERLAP: int = 200


settings = Settings()
