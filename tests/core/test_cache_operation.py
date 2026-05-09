"""Tests for remaining cache methods (mocked Redis)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.cache import RedisCache


@pytest.mark.asyncio
async def test_cache_connect():
    cache = RedisCache()
    with patch("app.core.cache.aioredis.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_from_url.return_value = mock_redis
        await cache.connect()
        assert cache._redis is not None
        mock_from_url.assert_called_once()


@pytest.mark.asyncio
async def test_cache_exists():
    cache = RedisCache()
    mock_redis = AsyncMock()
    mock_redis.exists.return_value = 1
    cache._redis = mock_redis
    assert await cache.exists("key") is True


@pytest.mark.asyncio
async def test_cache_flush():
    cache = RedisCache()
    mock_redis = AsyncMock()
    cache._redis = mock_redis
    await cache.flush()
    mock_redis.flushdb.assert_called_once()


@pytest.mark.asyncio
async def test_cache_disconnect():
    cache = RedisCache()
    mock_redis = AsyncMock()
    cache._redis = mock_redis
    await cache.disconnect()
    mock_redis.close.assert_called_once()
    assert cache._redis is None
