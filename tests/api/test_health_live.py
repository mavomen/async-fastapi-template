"""Test health check liveness endpoint."""

from fastapi.testclient import TestClient


def test_liveness_returns_alive(client: TestClient):
    """Liveness check returns status alive with timestamp."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data
