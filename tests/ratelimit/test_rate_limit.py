"""Tests for rate limiting.

Rate limiting is disabled in test mode (ENVIRONMENT=test),
so these tests verify that requests pass through normally.
"""

from fastapi.testclient import TestClient


def test_multiple_requests_not_blocked(client: TestClient):
    """Make multiple requests without hitting rate limits (disabled in test)."""
    for _ in range(10):
        response = client.get("/health")
        assert response.status_code in (200, 307)
