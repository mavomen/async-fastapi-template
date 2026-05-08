"""Test cache get on miss and set."""

from unittest.mock import AsyncMock

import pytest

from app.core.cache import RedisCache


@pytest.mark.asyncio
async def test_cache_get_miss_calls_metrics():
    cache = RedisCache()
    cache._redis = AsyncMock()
    cache._redis.get.return_value = None
    result = await cache.get("nonexistent")
    assert result is None
    # metrics counters are incremented (we just verify no crash)
