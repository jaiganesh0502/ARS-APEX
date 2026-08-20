from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Discharge Orchestration System"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "development-secret-key-change-in-production"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "discharge_orchestration"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/discharge_orchestration"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        elif isinstance(v, str) and v.startswith("["):
            import json
            return json.loads(v)
        return []

    # Integration Settings
    REPLICATE_API_TOKEN: str = ""
    LLM_MODEL: str = "openai/gpt-5.6-luna"
    LLM_REASONING_EFFORT: str = "low"
    LLM_VERBOSITY: str = "medium"
    LLM_MAX_COMPLETION_TOKENS: int = 3000

    # Orchestration & n8n
    ORCHESTRATION_MODE: str = "manual"  # "manual" | "n8n"
    N8N_BASE_URL: str = "http://localhost:5678"
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook/"
    N8N_WEBHOOK_SECRET: str = "change-me-in-production"
    INTERNAL_API_KEY: str = "change-me-in-production"
    N8N_TIMEOUT_SECONDS: float = 5.0
    N8N_MAX_RETRIES: int = 3

    MAPS_API_KEY: str = ""
    NOTIFICATION_SERVICE_URL: str = ""

    # Feature 9: Discharge Package & Storage Settings
    STORAGE_DIR: str = "storage/discharge-packages"
    PATIENT_SUMMARY_MODE: str = "mock"  # "mock" | "live"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
