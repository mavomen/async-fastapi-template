"""Tests for Scalar API reference."""

from fastapi.testclient import TestClient


def test_scalar_endpoint_accessible(client: TestClient):
    """Scalar documentation page loads."""
    response = client.get("/scalar")
    assert response.status_code == 200
    assert "api-reference" in response.text
