"""Tests for health check endpoints."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_health_check(client: TestClient):
    """Basic health check returns healthy status with timestamp."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_health_check_timestamp_format(client: TestClient):
    """Health check timestamp is valid ISO 8601 format."""
    response = client.get("/health")
    data = response.json()
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    now = datetime.now(UTC)
    assert abs((now - timestamp).total_seconds()) < 5


def test_health_check_response_schema(client: TestClient):
    """Health check returns exactly the expected keys."""
    response = client.get("/health")
    data = response.json()
    assert set(data.keys()) == {"status", "timestamp"}


def test_readiness_check(client: TestClient):
    """Readiness check confirms database connectivity, Redis may be absent."""
    response = client.get("/health/ready")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] in ("ready", "degraded")
    assert data["database"] == "connected"
    # Redis may be disconnected if no Redis server is running during tests
    assert data.get("redis") in ("connected", "disconnected", None)


def test_readiness_check_response_schema(client: TestClient):
    """Readiness check returns expected keys."""
    response = client.get("/health/ready")
    data = response.json()
    # Only assert required keys exist; redis is optional in test env
    assert "status" in data
    assert "database" in data


def test_liveness_check(client: TestClient):
    """Liveness check confirms service is alive."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


def test_liveness_check_timestamp_format(client: TestClient):
    """Liveness check timestamp is valid ISO 8601 format."""
    response = client.get("/health/live")
    data = response.json()
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    now = datetime.now(UTC)
    assert abs((now - timestamp).total_seconds()) < 5


def test_liveness_check_response_schema(client: TestClient):
    """Liveness check returns exactly the expected keys."""
    response = client.get("/health/live")
    data = response.json()
    assert set(data.keys()) == {"status", "timestamp"}


def test_dependencies_check(client: TestClient):
    """Detailed dependency check returns component status (DB required, Redis optional)."""
    response = client.get("/health/dependencies")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "components" in data
    assert data["components"]["database"] == "connected"
    # Redis may be disconnected in test env
    assert data["components"].get("redis") in ("connected", "disconnected", None)


@pytest.mark.asyncio
async def test_health_check_async(async_client: AsyncClient):
    """Health check works with async client."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_check_async(async_client: AsyncClient):
    """Readiness check works with async client."""
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ready", "degraded")
    assert data["database"] == "connected"
    assert data.get("redis") in ("connected", "disconnected", None)


@pytest.mark.asyncio
async def test_liveness_check_async(async_client: AsyncClient):
    """Liveness check works with async client."""
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data
