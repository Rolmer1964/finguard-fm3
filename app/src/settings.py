from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_SESSION_TOKEN: str | None = None

    # Combinação estratégica: barato para classificação, melhor para risco.
    BEDROCK_MODEL_TRIAGE: str = "anthropic.claude-3-haiku-20240307-v1:0"
    BEDROCK_MODEL_RISK: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # Embeddings para o RAG (Titan v2: 1024 dim, normalizado)
    BEDROCK_EMBED_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    EMBED_DIM: int = 1024

    OUTPUT_DIR: str = "/app/output"

    # ---- RAG (sempre ativo no nível 2 — alimenta o agente de risco) ----
    RAG_DOCS_DIR: str = "/app/assets/docs"
    RAG_INDEX_DIR: str = "/app/assets/index"
    RAG_TOP_K: int = 4
    RAG_CHUNK_CHARS: int = 1000
    RAG_CHUNK_OVERLAP: int = 200


settings = Settings()
