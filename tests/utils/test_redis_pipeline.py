"""Tests for Redis pipeline utilities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.utils.redis_pipeline import batch_get, batch_set


@pytest.mark.asyncio
async def test_batch_set():
    redis = AsyncMock()
    pipe = MagicMock()
    redis.pipeline = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock()
    await batch_set(redis, {"key1": "val1", "key2": "val2"}, ttl=60)
    assert redis.pipeline.called
    assert pipe.setex.call_count == 2
    pipe.execute.assert_called_once()


@pytest.mark.asyncio
async def test_batch_get():
    redis = AsyncMock()
    pipe = MagicMock()
    redis.pipeline = MagicMock(return_value=pipe)
    # simulate async execute returning a list of bytes
    pipe.execute = AsyncMock(return_value=[b'"a"', b'"b"'])
    result = await batch_get(redis, ["x", "y"])
    assert redis.pipeline.called
    assert pipe.get.call_count == 2
    assert result == {"x": "a", "y": "b"}
