"""Tests for logging middleware."""

import pytest
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware


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
    # Verify middleware exists by checking user_middleware
    middleware_classes = [m.cls for m in app.user_middleware]
    from app.middleware.request_logging import RequestLoggingMiddleware as RL
    assert RL in middleware_classes
