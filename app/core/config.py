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
    DB_POOL_SIZE: int | None = Field(
        default=None,
        description="Asyncpg pool base size. When unset, resolved per environment (dev=10, staging=20, prod=40).",
    )
    DB_MAX_OVERFLOW: int | None = Field(
        default=None,
        description="Asyncpg pool max overflow. When unset, resolved per environment (dev=5, staging=10, prod=20).",
    )
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_SATURATION_THRESHOLD: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Pool saturation ratio that triggers a warning alert",
    )

    _POOL_PRESETS: dict[str, tuple[int, int]] = {
        "development": (10, 5),
        "staging": (20, 10),
        "production": (40, 20),
    }

    @property
    def effective_pool_size(self) -> int:
        """Resolve pool size: explicit env var > per-environment preset."""
        if self.DB_POOL_SIZE is not None:
            return self.DB_POOL_SIZE
        return self._POOL_PRESETS.get(self.ENVIRONMENT, (20, 10))[0]

    @property
    def effective_max_overflow(self) -> int:
        """Resolve max overflow: explicit env var > per-environment preset."""
        if self.DB_MAX_OVERFLOW is not None:
            return self.DB_MAX_OVERFLOW
        return self._POOL_PRESETS.get(self.ENVIRONMENT, (20, 10))[1]

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

    # Rate Limiting (Redis sliding-window tiers)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_SENSITIVE: int = 5
    RATE_LIMIT_PUBLIC: int = 20
    RATE_LIMIT_AUTHENTICATED: int = 100
    RATE_LIMIT_ADMIN: int = 300

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
    CDN_DOMAIN: str = ""

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    OTEL_SERVICE_NAME: str = "fastapi-app"
    OTEL_SAMPLE_RATE: float = Field(default=1.0, ge=0.0, le=1.0)

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

    # OAuth2 / Social Login
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITLAB_CLIENT_ID: str = ""
    GITLAB_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_URL: str = "http://localhost:8000/api/v1/auth/oauth/callback"
    OAUTH_STATE_EXPIRE_SECONDS: int = 300
    OAUTH_AUTO_LINK: bool = True

    # Compression
    COMPRESSION_ENABLED: bool = True
    COMPRESSION_MIN_SIZE: int = 1024
    COMPRESSION_LEVEL: int = 6

    # HTTP Client (shared connection pool)
    HTTP_CLIENT_TIMEOUT: int = 30
    HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS: int = 10
    HTTP_CLIENT_KEEPALIVE_EXPIRY: int = 300

    # Outgoing Webhooks
    WEBHOOK_ENABLED: bool = True
    WEBHOOK_MAX_RETRIES: int = Field(
        default=5, ge=0, description="Max delivery retries per webhook after the initial attempt"
    )
    WEBHOOK_BACKOFF_BASE_SECONDS: float = Field(
        default=60.0, ge=0, description="Base delay (s) for exponential retry backoff"
    )
    WEBHOOK_BACKOFF_MAX_SECONDS: float = Field(
        default=3600.0, ge=0, description="Cap (s) for exponential retry backoff"
    )
    WEBHOOK_TIMEOUT_SECONDS: int = Field(
        default=10, ge=1, description="HTTP timeout for outbound webhook deliveries"
    )
    WEBHOOK_SIGNATURE_TOLERANCE_SECONDS: int = Field(
        default=300, ge=0, description="Max age (s) of a webhook signature timestamp"
    )

    # Notification preferences & channels
    NOTIFICATION_ENABLED: bool = Field(
        default=True, description="Enable the notification dispatcher on the event bus"
    )

    # Database Backup
    BACKUP_S3_PREFIX: str = Field(
        default="backups/",
        description="S3 key prefix for database backups",
    )
    BACKUP_RETENTION_DAYS: int = Field(
        default=30, ge=1, description="Number of days to retain database backups in S3"
    )

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
