"""FastAPI application factory and configuration."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from scalar_fastapi import get_scalar_api_reference
from strawberry.fastapi import GraphQLRouter

from app.admin import router as admin_router
from app.api import api_router
from app.api.deps import get_gql_context
from app.api.error_handlers import configure_exception_handlers
from app.api.health import k8s_router
from app.api.health import router as health_router
from app.auth.profile import router as profile_router
from app.core.cache import cache
from app.core.config import settings
from app.core.database import sessionmanager
from app.core.http_client import http_client
from app.core.logging import setup_logging
from app.core.tracing import setup_tracing
from app.gql import router as gql_playground_router
from app.gql.schema import schema
from app.i18n.middleware import LocaleMiddleware
from app.middleware.api_versioning import APIVersioningMiddleware
from app.middleware.compression import CompressionMiddleware
from app.middleware.correlation import CorrelationIDMiddleware
from app.middleware.csrf import CSRFTokenMiddleware
from app.middleware.error_logging import error_logging_middleware
from app.middleware.query_count import QueryCountMiddleware
from app.middleware.redis_rate_limit import RedisRateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.request_timeout import RequestTimeoutMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.sql_injection import SQLInjectionMonitorMiddleware
from app.middleware.tenant import TenantMiddleware
from app.middleware.tenant_ip_access import TenantIPAccessMiddleware
from app.websocket.chat import router as websocket_router

# Global drain flag — readiness probe returns 503 once set.
_draining = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events.

    On SIGTERM / uvicorn shutdown the context manager exits; we set the drain
    flag and wait up to 30 s for in-flight HTTP requests to complete before
    tearing down DB / cache connections.
    """
    # Startup
    sessionmanager.init(
        writer_url=settings.DATABASE_URL,
        reader_url=settings.DATABASE_URL_READER,
    )
    await cache.connect()
    await http_client.connect()
    if settings.ENVIRONMENT != "test":
        from app.models.audit_log import install_audit_log_listener
        from app.models.user import User

        install_audit_log_listener(User)
        await TenantMiddleware.warm_default_tenant()
        if settings.WEBHOOK_ENABLED:
            await _subscribe_webhook_dispatcher()
        if settings.NOTIFICATION_ENABLED:
            await _subscribe_notification_dispatcher()
    yield
    # Begin draining — readiness probe starts returning 503
    _draining.set()
    # Give in-flight requests a window to finish (uvicorn's own timeout acts as
    # the hard ceiling, this is the soft ceiling).
    with suppress(TimeoutError):
        await asyncio.wait_for(_draining.wait(), timeout=15)
    # Shutdown: only close in non-test environments
    if settings.ENVIRONMENT != "test":
        from app.core.tracing import shutdown_tracing

        shutdown_tracing()
        await sessionmanager.close()
        await cache.disconnect()
        await http_client.disconnect()


async def _subscribe_webhook_dispatcher() -> None:
    """Subscribe the webhook dispatcher to every event bus message.

    Swallowed on failure so an unreachable event bus never blocks startup.
    """
    import logging

    from app.events import get_event_bus
    from app.services.webhook import handle_event

    logger = logging.getLogger("app.main")
    try:
        bus = await get_event_bus()
        await bus.subscribe("*", handle_event)
    except Exception:
        logger.exception("Failed to subscribe webhook dispatcher to event bus")


async def _subscribe_notification_dispatcher() -> None:
    """Subscribe the notification dispatcher to every event bus message.

    Swallowed on failure so an unreachable event bus never blocks startup.
    """
    import logging

    from app.events import get_event_bus
    from app.services.notifications import handle_notification_event

    logger = logging.getLogger("app.main")
    try:
        bus = await get_event_bus()
        await bus.subscribe("*", handle_notification_event)
    except Exception:
        logger.exception("Failed to subscribe notification dispatcher to event bus")


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
            {
                "name": "admin",
                "description": "HTMX-powered admin dashboard for managing application data.",
            },
            {
                "name": "profile",
                "description": "User profile management endpoints.",
            },
            {
                "name": "tenants",
                "description": "Multi-tenant management endpoints.",
            },
            {
                "name": "events",
                "description": "Event bus monitoring and management endpoints.",
            },
            {
                "name": "websocket",
                "description": "WebSocket chat endpoints with JWT authentication.",
            },
            {
                "name": "graphql",
                "description": "GraphQL endpoint for queries, mutations, and subscriptions.",
            },
            {
                "name": "webhooks",
                "description": "Outgoing webhook registration, delivery, and history.",
            },
            {
                "name": "notifications",
                "description": "Per-user notification preferences and in-app inbox.",
            },
        ],
    )

    configure_exception_handlers(app)

    # Request timeout (must be outermost — wraps the full request lifecycle)
    app.add_middleware(RequestTimeoutMiddleware, timeout=30)

    # Compression middleware (early — compresses final response body)
    app.add_middleware(CompressionMiddleware)

    # Correlation ID middleware (must be added early)
    app.add_middleware(CorrelationIDMiddleware)

    app.add_middleware(QueryCountMiddleware)

    # Request ID injection into logs and traces
    app.add_middleware(RequestIDMiddleware)

    # Locale resolution (Accept-Language / ?lang= override)
    app.add_middleware(LocaleMiddleware)

    # Redis-backed sliding-window rate limiting (supports per-endpoint tiers)
    app.add_middleware(RedisRateLimitMiddleware)

    # Request/response logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Error logging (catch all)
    app.middleware("http")(error_logging_middleware)

    # Security middlewares
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFTokenMiddleware)
    app.add_middleware(SQLInjectionMonitorMiddleware)

    # API versioning middleware (adds X-API-Version header)
    app.add_middleware(APIVersioningMiddleware)

    # Tenant resolution middleware (after security, before CORS)
    app.add_middleware(TenantMiddleware)

    # IP access control per tenant (after tenant resolution)
    app.add_middleware(TenantIPAccessMiddleware)

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
    app.include_router(k8s_router)  # /healthz, /readyz at root level
    app.include_router(admin_router, prefix="/admin", tags=["admin"])
    app.include_router(profile_router, prefix="/profile", tags=["profile"])
    app.include_router(api_router, prefix=settings.API_V1_STR)
    app.include_router(websocket_router)

    # API v2 router (opt-in via API_V2_ENABLED)
    if settings.API_V2_ENABLED:
        from app.api.v2 import api_v2_router

        app.include_router(api_v2_router, prefix="/api/v2", tags=["v2"])
        app.title = f"{settings.PROJECT_NAME} (v1+v2)"
    else:
        app.title = f"{settings.PROJECT_NAME} (v1)"
    app.include_router(gql_playground_router, prefix="/gql", tags=["graphql"])

    # Scalar API reference (modern, dark-mode capable)
    @app.get("/scalar", include_in_schema=False)
    async def scalar_html() -> Any:
        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=settings.PROJECT_NAME,
        )

    # Prometheus metrics
    from app.core.metrics import instrumentator

    instrumentator.instrument(app).expose(app, endpoint="/metrics")

    # OpenTelemetry tracing (after all routes)
    setup_tracing(app)

    # GraphQL endpoint
    graphql_app = GraphQLRouter(
        schema,
        context_getter=get_gql_context,  # type: ignore[arg-type]
    )
    app.include_router(graphql_app, prefix="/graphql")
    return app


app = create_app()
