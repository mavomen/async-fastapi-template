"""Application configuration management."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        frozen=True,
    )

    # Application
    PROJECT_NAME: str = "FastAPI Async Template"
    VERSION: str = "3.0.0"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db",
        description="PostgreSQL connection string with asyncpg driver",
    )

    # Redis (application cache)
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for application cache",
    )

    # Celery / Redis
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/2",
        description="Redis broker URL for Celery",
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        description="Redis result backend for Celery",
    )

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    RATE_LIMIT_PER_DAY: int = 10000

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = {"development", "staging", "production", "test"}
        if v not in valid_envs:
            raise ValueError(f"ENVIRONMENT must be one of {valid_envs}")
        return v

    # File Storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_PATH: str = "./uploads"
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None

    FRONTEND_URL: str = "http://localhost:3000"

    # Performance
    SLOW_QUERY_THRESHOLD_MS: int = 500  # Log queries slower than this

    # Event Bus
    EVENT_BUS_BACKEND: Literal["redis", "kafka"] = "redis"
    EVENT_BUS_REDIS_URL: str | None = None
    EVENT_BUS_KAFKA_SERVERS: str = "localhost:9092"

    # WebAuthn
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "FastAPI Async Template"
    WEBAUTHN_ORIGIN: str = "http://localhost:8000"
    WEBAUTHN_RELYING_PARTY_ID: str = "localhost"  # alias for RP ID


settings = Settings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
