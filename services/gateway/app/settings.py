from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    JWT_SECRET: str
    JWT_ALG: str = "HS256"

    AUTH_SERVICE_URL: str
    COMPLAINT_SERVICE_URL: str
    ORCHESTRATOR_URL: str
    REPORT_SERVICE_URL: str


settings = Settings()
