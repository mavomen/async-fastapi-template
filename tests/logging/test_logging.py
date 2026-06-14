"""Tests for logging middleware and context."""

from fastapi.testclient import TestClient

from app.middleware.request_logging import RequestLoggingMiddleware


def test_correlation_id_injected(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers


def test_correlation_id_forwarded(client: TestClient):
    response = client.get("/health", headers={"X-Correlation-ID": "my-custom-id"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "my-custom-id"


def test_request_logging_middleware_present():
    """RequestLoggingMiddleware is registered."""
    from app.main import app

    middleware_classes = [m.cls for m in app.user_middleware]

    assert RequestLoggingMiddleware in middleware_classes


def test_logcontext_does_not_clear_outer_context():
    """LogContext should unbind only its own keys, not all context vars."""
    import structlog

    from app.logging.context import LogContext

    structlog.contextvars.bind_contextvars(outer_key="outer_value")

    with LogContext(inner_key="inner_value"):
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("inner_key") == "inner_value"
        assert ctx.get("outer_key") == "outer_value"

    ctx_after = structlog.contextvars.get_contextvars()
    assert ctx_after.get("outer_key") == "outer_value"
    assert "inner_key" not in ctx_after

    structlog.contextvars.clear_contextvars()
