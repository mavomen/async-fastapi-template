"""Tests for health check endpoints."""

from datetime import UTC, datetime, timedelta

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
    """Readiness check confirms database connectivity."""
    response = client.get("/health/ready")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_readiness_check_response_schema(client: TestClient):
    """Readiness check returns exactly the expected keys."""
    response = client.get("/health/ready")
    data = response.json()

    assert set(data.keys()) == {"status", "database"}


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


def test_health_endpoints_independent_timestamps(client: TestClient):
    """Multiple calls to timestamp endpoints produce different values."""
    response1 = client.get("/health")
    response2 = client.get("/health")

    ts1 = response1.json()["timestamp"]
    ts2 = response2.json()["timestamp"]

    assert isinstance(ts1, str)
    assert isinstance(ts2, str)


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
    assert data["status"] == "ready"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_liveness_check_async(async_client: AsyncClient):
    """Liveness check works with async client."""
    response = await async_client.get("/health/live")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data
