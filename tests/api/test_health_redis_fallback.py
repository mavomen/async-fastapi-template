"""Cover the health check Redis fallback branch."""

import pytest
from fastapi.testclient import TestClient


def test_health_check_redis_not_cached(client: TestClient):
    """Readiness returns even when Redis is not connected."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    # Status can be ready or degraded depending on Redis availability
    assert response.json()["status"] in ("ready", "degraded")
