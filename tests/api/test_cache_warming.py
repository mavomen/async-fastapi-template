"""Tests for cache warming and cache-aside pattern."""

from unittest.mock import AsyncMock, patch

import pytest

from app.utils.cache_warming import cache_aside, warm_cache


@pytest.mark.asyncio
async def test_cache_aside_uses_cache_when_present():
    with (
        patch("app.utils.cache_warming.cache.get", new_callable=AsyncMock) as mock_get,
        patch("app.utils.cache_warming.cache.set", new_callable=AsyncMock) as mock_set,
    ):
        mock_get.return_value = {"cached": True}
        fetch = AsyncMock()
        result = await cache_aside("test", fetch, ttl=60)
        assert result == {"cached": True}
        fetch.assert_not_called()
        mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_cache_aside_fetches_on_miss():
    with (
        patch("app.utils.cache_warming.cache.get", new_callable=AsyncMock) as mock_get,
        patch("app.utils.cache_warming.cache.set", new_callable=AsyncMock) as mock_set,
    ):
        mock_get.return_value = None
        fetch = AsyncMock(return_value={"fresh": "data"})
        result = await cache_aside("test", fetch, ttl=120)
        assert result == {"fresh": "data"}
        fetch.assert_called_once()
        mock_set.assert_called_once_with("test", {"fresh": "data"}, ttl=120)


@pytest.mark.asyncio
async def test_warm_cache_calls_all_fetchers():
    async def fetcher_a():
        return "a"

    async def fetcher_b():
        return "b"

    keys = {"a": fetcher_a, "b": fetcher_b}
    with (
        patch("app.utils.cache_warming.cache.get", new_callable=AsyncMock) as mock_get,
        patch("app.utils.cache_warming.cache.set", new_callable=AsyncMock) as mock_set,
    ):
        mock_get.return_value = None
        await warm_cache(keys)
        assert mock_get.call_count == 2
        assert mock_set.call_count == 2
