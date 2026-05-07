"""Tests for Redis cache connectivity and operations."""

import pytest
from unittest.mock import AsyncMock, patch

from app.core.cache import cache


@pytest.mark.asyncio
async def test_cache_connect_calls_from_url():
    """Connect should create a Redis client via aioredis.from_url."""
    mock_client = AsyncMock()
    with patch("app.core.cache.aioredis.from_url", return_value=mock_client) as mock_from_url:
        await cache.connect()
        mock_from_url.assert_called_once()
        # The internal _redis reference should be set
        # We can't access it directly, but the mock was called
    await cache.disconnect()


@pytest.mark.asyncio
async def test_cache_set_get_delete_with_mock():
    """Set, get, delete should delegate to the Redis client."""
    mock_client = AsyncMock()
    mock_client.get.return_value = '{"a": 1}'

    with patch.object(cache, "_redis", mock_client):
        await cache.set("key", {"a": 1}, ttl=10)
        mock_client.setex.assert_called_once_with("key", 10, '{"a": 1}')

        result = await cache.get("key")
        assert result == {"a": 1}
        mock_client.get.assert_called_once_with("key")

        await cache.delete("key")
        mock_client.delete.assert_called_once_with("key")
