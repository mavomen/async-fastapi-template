"""Middleware that injects the correlation ID into log context and OpenTelemetry spans."""

import structlog
from fastapi import Request
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject correlation ID into structlog and OpenTelemetry."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = getattr(request.state, "correlation_id", None)
        if correlation_id:
            structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
            # Set OpenTelemetry span attribute
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_attribute("correlation_id", correlation_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        return response
