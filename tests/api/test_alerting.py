"""Tests for alerting config and health check extensions."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.core.config import get_settings


def test_settings_has_alerting_fields() -> None:
    """Settings exposes SLACK_WEBHOOK_URL and PAGERDUTY_KEY."""
    settings = get_settings()
    assert hasattr(settings, "SLACK_WEBHOOK_URL")
    assert hasattr(settings, "PAGERDUTY_KEY")
    assert isinstance(settings.SLACK_WEBHOOK_URL, str)
    assert isinstance(settings.PAGERDUTY_KEY, str)


def test_readiness_includes_event_bus(client: TestClient) -> None:
    """Readiness check now includes event_bus field."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ready", "degraded")
    assert "event_bus" in data


def test_dependencies_includes_event_bus(client: TestClient) -> None:
    """Dependencies check now includes event_bus component."""
    response = client.get("/health/dependencies")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "event_bus" in data["components"]


def test_liveness_unchanged(client: TestClient) -> None:
    """Liveness check is unaffected by alerting changes."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness_async_event_bus(async_client: AsyncClient) -> None:
    """Async readiness check also includes event_bus."""
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert "event_bus" in data
    assert data.get("event_bus") in ("connected", "disconnected", "unknown")
