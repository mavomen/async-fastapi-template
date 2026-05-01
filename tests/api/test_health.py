"""Tests for health check endpoints."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_health_check(client: TestClient) -> None:
    """Test basic health check endpoint."""
    response = client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "async-fastapi-template"


def test_readiness_check(client: TestClient) -> None:
    """Test readiness check endpoint."""
    response = client.get("/health/ready")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ready"
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis" in data["checks"]


def test_liveness_check(client: TestClient) -> None:
    """Test liveness check endpoint."""
    response = client.get("/health/live")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "alive"


@pytest.mark.asyncio
async def test_health_check_async(async_client: AsyncClient) -> None:
    """Test basic health check endpoint with async client."""
    response = await async_client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "async-fastapi-template"


@pytest.mark.asyncio
async def test_readiness_check_async(async_client: AsyncClient) -> None:
    """Test readiness check endpoint with async client."""
    response = await async_client.get("/health/ready")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ready"
    assert "checks" in data


@pytest.mark.asyncio
async def test_liveness_check_async(async_client: AsyncClient) -> None:
    """Test liveness check endpoint with async client."""
    response = await async_client.get("/health/live")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "alive"
