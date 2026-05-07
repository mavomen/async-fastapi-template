"""FastAPI application factory and configuration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from strawberry.fastapi import GraphQLRouter

from app.api import api_router
from app.api.deps import get_gql_context
from app.api.error_handlers import configure_exception_handlers
from app.api.health import router as health_router
from app.core.cache import cache
from app.core.config import settings
from app.core.database import sessionmanager
from app.core.logging import setup_logging
from app.core.tracing import setup_tracing
from app.gql.schema import schema
from app.middleware.correlation import CorrelationIDMiddleware
from app.middleware.error_logging import error_logging_middleware
from app.middleware.rate_limit import configure_rate_limit
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.sql_injection import SQLInjectionMonitorMiddleware
from app.websocket.chat import router as websocket_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events."""
    # Startup
    sessionmanager.init(settings.DATABASE_URL)
    await cache.connect()
    yield
    # Shutdown: only close in non‑test environments
    if settings.ENVIRONMENT != "test":
        await sessionmanager.close()
        await cache.disconnect()


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
        openapi_tags=[
            {
                "name": "health",
                "description": "Health check endpoints for readiness, liveness, and dependencies.",
            },
            {
                "name": "auth",
                "description": "User registration and JWT token authentication.",
            },
            {
                "name": "users",
                "description": "User management with role-based access control (RBAC).",
            },
            {
                "name": "tasks",
                "description": "Background task trigger and status endpoints.",
            },
            {
                "name": "files",
                "description": "File upload and download with local or S3 storage.",
            },
            {"name": "metrics", "description": "Prometheus metrics endpoint."},
        ],
    )

    configure_exception_handlers(app)
    configure_rate_limit(app)

    # Correlation ID middleware (must be added early)
    app.add_middleware(CorrelationIDMiddleware)

    # Request/response logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Error logging (catch all)
    app.middleware("http")(error_logging_middleware)

    # Security middlewares
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SQLInjectionMonitorMiddleware)

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

    # Prometheus metrics
    from app.core.metrics import instrumentator

    instrumentator.instrument(app).expose(app, endpoint="/metrics")

    # OpenTelemetry tracing (after all routes)
    setup_tracing(app)

    # GraphQL endpoint
    graphql_app = GraphQLRouter(schema, context_getter=get_gql_context)
    app.include_router(graphql_app, prefix="/graphql")
    return app


app = create_app()
