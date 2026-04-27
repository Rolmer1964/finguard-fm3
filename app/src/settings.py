from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_SESSION_TOKEN: str | None = None

    BEDROCK_MODEL_ID: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    BEDROCK_EMBED_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    EMBED_DIM: int = 1024

    OUTPUT_DIR: str = "/app/output"

    # ---- RAG ----
    # Pasta com PDFs/MDs/TXTs de política interna (montada como volume)
    RAG_DOCS_DIR: str = "/app/assets/docs"
    # Pasta onde o índice FAISS + manifest são persistidos
    RAG_INDEX_DIR: str = "/app/assets/index"
    # Quando True, o classificador inclui trechos relevantes da política como contexto
    RAG_ENABLED: bool = False
    # Quantos trechos top-K injetar quando RAG_ENABLED
    RAG_TOP_K: int = 3
    # Tamanho-alvo de cada chunk em caracteres (~250 tokens)
    RAG_CHUNK_CHARS: int = 1000
    RAG_CHUNK_OVERLAP: int = 200


settings = Settings()
