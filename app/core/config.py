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
    VERSION: str = "3.1.0"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db",
        description="PostgreSQL primary connection string with asyncpg driver",
    )
    DATABASE_URL_READER: str | None = Field(
        default=None,
        description="PostgreSQL read-replica connection string. Falls back to DATABASE_URL when unset.",
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_SATURATION_THRESHOLD: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Pool saturation ratio that triggers a warning alert",
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
    RATE_LIMIT_ENABLED: bool = True

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
    DB_SLOW_QUERY_CAPTURE_EXPLAIN: bool = Field(
        default=False,
        description="Run EXPLAIN (FORMAT JSON) on slow SELECT queries and log the plan",
    )
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100

    # Event Bus
    EVENT_BUS_BACKEND: Literal["redis", "kafka"] = "redis"
    EVENT_BUS_REDIS_URL: str | None = None
    EVENT_BUS_KAFKA_SERVERS: str = "localhost:9092"

    # TOTP / 2FA
    TOTP_ISSUER_NAME: str = "FastAPI Async Template"
    TOTP_CODE_EXPIRE_SECONDS: int = 30
    TOTP_CODE_LENGTH: int = 6
    TOTP_BACKUP_CODE_COUNT: int = 8
    TOTP_CHALLENGE_EXPIRE_SECONDS: int = 120

    # WebAuthn
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "FastAPI Async Template"
    WEBAUTHN_ORIGIN: str = "http://localhost:8000"

    # Brute-force lockout
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Passwordless magic links
    MAGIC_LINK_EXPIRE_MINUTES: int = 15
    MAGIC_LINK_ALLOW_REGISTRATION: bool = True

    # API Keys (service-to-service)
    API_KEY_LENGTH_BYTES: int = 32
    API_KEY_EXPIRE_DAYS: int = 365

    # JWT Blacklist / Revocation
    JWT_BLACKLIST_ENABLED: bool = True
    JWT_BLACKLIST_TTL: int = 86400  # 24h — max age to keep revoked tokens

    # Content Security Policy
    CSP_REPORT_URI: str = "/api/v1/csp-report"
    CSP_REPORT_ONLY: bool = False
    CSP_DEFAULT_SRC: str = "'self'"
    CSP_SCRIPT_SRC: str = "'self' 'unsafe-inline'"
    CSP_STYLE_SRC: str = "'self' 'unsafe-inline'"
    CSP_IMG_SRC: str = "'self' data:"
    CSP_CONNECT_SRC: str = "'self'"
    CSP_FRAME_ANCESTORS: str = "'none'"
    CSP_FORM_ACTION: str = "'self'"


settings = Settings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
