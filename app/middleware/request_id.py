"""Middleware that injects the correlation ID, trace_id, and span_id into log context."""

import structlog
from fastapi import Request
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = structlog.get_logger(__name__)


def _span_to_ids(span: trace.Span) -> tuple[str, str]:
    """Extract trace_id and span_id hex strings from the current span."""
    ctx = span.get_span_context()
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject correlation ID, trace_id, and span_id into structlog context and OpenTelemetry."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = getattr(request.state, "correlation_id", None)
        bind: dict[str, str] = {}
        if correlation_id:
            bind["correlation_id"] = correlation_id

        # Extract trace/span IDs for log-to-trace correlation
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            trace_id, span_id = _span_to_ids(current_span)
            bind["trace_id"] = trace_id
            bind["span_id"] = span_id
            if correlation_id:
                current_span.set_attribute("correlation_id", correlation_id)

        if bind:
            structlog.contextvars.bind_contextvars(**bind)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        return response
