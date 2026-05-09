"""Tests for per-user rate limiting."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rate_limit_headers_present(async_client: AsyncClient):
    """Rate limit headers are returned for any request."""
    resp = await async_client.get("/health")
    assert "X-RateLimit-Limit" in resp.headers or "x-ratelimit-limit" in resp.headers
