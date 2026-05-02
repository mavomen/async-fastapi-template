"""FastAPI application factory and configuration."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api import api_router
from app.api.health import router as health_router
from app.core.config import settings
from app.core.database import sessionmanager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events.

    Handles startup and shutdown operations including:
    - Database connection initialization and cleanup
    """
    # Startup
    sessionmanager.init(settings.DATABASE_URL)

    yield

    # Shutdown: only close in non‑test environments
    if settings.ENVIRONMENT != "test":
        await sessionmanager.close()


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check routes (no version prefix)
    app.include_router(health_router, prefix="/health", tags=["health"])

    # Versioned API routes
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_app()
