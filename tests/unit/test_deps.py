"""Unit tests for FastAPI dependencies (get_cache, get_storage)."""

import pytest

from app.api.deps import get_cache, get_storage
from app.core.cache import RedisCache
from app.storage.local import LocalStorage


@pytest.mark.asyncio
async def test_get_cache_returns_redis_cache_instance():
    """get_cache should return a RedisCache instance."""
    result = await get_cache()
    assert isinstance(result, RedisCache)


@pytest.mark.asyncio
async def test_get_storage_returns_local_storage_by_default(monkeypatch):
    """When STORAGE_BACKEND is 'local', get_storage returns LocalStorage."""
    from app.core import config

    mock_settings = config.Settings(
        ENVIRONMENT="test",
        SECRET_KEY="a" * 32,
        STORAGE_BACKEND="local",
        LOCAL_STORAGE_PATH="/tmp/test",
    )
    monkeypatch.setattr(config, "settings", mock_settings)
    storage = await get_storage()
    assert isinstance(storage, LocalStorage)
