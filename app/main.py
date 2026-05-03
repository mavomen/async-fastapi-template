"""FastAPI application factory and configuration."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api import api_router
from app.api.health import router as health_router
from app.api.error_handlers import configure_exception_handlers
from app.middleware.error_logging import error_logging_middleware
from app.middleware.rate_limit import configure_rate_limit
from app.middleware.correlation import CorrelationIDMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.core.config import settings
from app.core.database import sessionmanager
from app.core.logging import setup_logging
from app.websocket.chat import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events."""
    # Startup
    sessionmanager.init(settings.DATABASE_URL)
    yield
    # Shutdown: only close in non‑test environments
    if settings.ENVIRONMENT != "test":
        await sessionmanager.close()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    setup_logging()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    configure_exception_handlers(app)
    configure_rate_limit(app)

    # Correlation ID middleware (must be added early)
    app.add_middleware(CorrelationIDMiddleware)

    # Request/response logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Error logging (catch all)
    app.middleware("http")(error_logging_middleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health_router, prefix="/health", tags=["health"])
    app.include_router(api_router, prefix=settings.API_V1_STR)
    app.include_router(websocket_router)

    return app


app = create_app()
