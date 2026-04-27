from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_SESSION_TOKEN: str | None = None

    BEDROCK_MODEL_ID: str = "anthropic.claude-3-haiku-20240307-v1:0"

    OUTPUT_DIR: str = "/app/output"


settings = Settings()
