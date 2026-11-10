from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(
        default="Arham Fintech BSE Trade Dashboard API",
        description="Human-readable service name exposed in OpenAPI metadata.",
    )
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    database_url: str = Field(default="sqlite:///./data/trades.db")
    seed_trade_count: int = Field(default=3250, ge=0)

    bse_pull_delay_seconds: float = Field(default=900.0, ge=0.0)
    bse_default_batch_size: int = Field(default=50, ge=1, le=1000)
    bse_max_retries: int = Field(default=2, ge=0, le=10)
    bse_retry_delay_seconds: float = Field(default=2.0, ge=0.0)

    sse_heartbeat_seconds: float = Field(default=15.0, gt=0.0)

    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated list of allowed CORS origins.",
    )

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            return "INFO"
        return normalized

    @property
    def cors_origin_list(self) -> List[str]:
        origins = [item.strip().rstrip("/") for item in self.cors_origins.split(",") if item.strip()]
        return origins or ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
