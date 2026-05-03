"""Tests for rate limiting."""

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient


def test_rate_limit_headers_present(client: TestClient):
    """Check that rate limit headers are present after a request."""
    response = client.get("/health")
    assert response.status_code == 200
    # slowapi injects these headers (case may vary)
    assert any(h.lower().startswith("x-ratelimit") for h in response.headers.keys())


def test_multiple_requests_not_blocked(client: TestClient):
    """Make multiple requests without exceeding high default limit."""
    for _ in range(10):
        response = client.get("/health")
        assert response.status_code == 200
