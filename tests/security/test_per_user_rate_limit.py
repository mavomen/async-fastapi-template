"""Tests for per-user rate limiting.

Rate limiting is disabled in test mode (ENVIRONMENT=test),
so these tests verify that requests pass through normally.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_passes(async_client: AsyncClient):
    """Health endpoint returns normally (rate limiting disabled in test mode)."""
    resp = await async_client.get("/health")
    assert resp.status_code in (200, 307)
