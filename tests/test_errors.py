"""Tests for exception handlers and custom errors."""

from fastapi.testclient import TestClient


def test_404_route(client: TestClient):
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_validation_error(client: TestClient):
    # Trigger validation error by sending invalid data to register endpoint
    response = client.post("/api/v1/auth/register", json={"bad": "data"})
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == "Validation error"
    assert "errors" in data
    assert isinstance(data["errors"], list)
    err = data["errors"][0]
    assert "field" in err
    assert "message" in err
    assert "type" in err
