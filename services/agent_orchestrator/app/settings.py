from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_SESSION_TOKEN: str | None = None

    BEDROCK_MODEL_TRIAGE: str
    BEDROCK_MODEL_RISK: str
    BEDROCK_MODEL_REPORT: str

    BEDROCK_GUARDRAIL_ID: str | None = None
    BEDROCK_GUARDRAIL_VERSION: str = "DRAFT"

    POLICY_PATH: str = "/app/data/politica_interna.md"


settings = Settings()
