"""Tests for Redis sliding-window rate limiter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.rate_limiter import RedisSlidingWindowLimiter


@pytest.fixture
def limiter():
    return RedisSlidingWindowLimiter()


@pytest.fixture
def mock_pipe():
    pipe = AsyncMock()
    pipe.zremrangebyscore.return_value = 1
    pipe.zadd.return_value = 1
    pipe.zcard.return_value = 3
    pipe.expire.return_value = True
    pipe.execute.return_value = [1, 1, 3, True]
    return pipe


@pytest.mark.asyncio
async def test_allows_request_within_limit(limiter, mock_pipe):
    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    with patch.object(limiter, "_get_redis", return_value=mock_redis):
        result = await limiter.check("test:key", 10, 60)

    assert result.allowed is True
    assert result.remaining == 7
    assert result.reset > 0


@pytest.mark.asyncio
async def test_blocks_request_over_limit(limiter):
    mock_pipe = AsyncMock()
    mock_pipe.zremrangebyscore.return_value = 5
    mock_pipe.zadd.return_value = 1
    mock_pipe.zcard.return_value = 11
    mock_pipe.expire.return_value = True
    mock_pipe.execute.return_value = [5, 1, 11, True]

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    with patch.object(limiter, "_get_redis", return_value=mock_redis):
        result = await limiter.check("test:blocked", 10, 60)

    assert result.allowed is False
    assert result.remaining == 0


@pytest.mark.asyncio
async def test_remaining_at_window_boundary(limiter):
    mock_pipe = AsyncMock()
    mock_pipe.zremrangebyscore.return_value = 1
    mock_pipe.zadd.return_value = 1
    mock_pipe.zcard.return_value = 10
    mock_pipe.expire.return_value = True
    mock_pipe.execute.return_value = [1, 1, 10, True]

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    with patch.object(limiter, "_get_redis", return_value=mock_redis):
        result = await limiter.check("test:boundary", 10, 60)

    assert result.allowed is True
    assert result.remaining == 0


@pytest.mark.asyncio
async def test_reset_returns_positive_int(limiter):
    mock_pipe = AsyncMock()
    mock_pipe.execute.return_value = [0, 1, 1, True]

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    with patch.object(limiter, "_get_redis", return_value=mock_redis):
        result = await limiter.check("test:reset", 10, 60)

    assert result.allowed is True
    assert isinstance(result.reset, int)
    assert result.reset > 0


@pytest.mark.asyncio
async def test_uses_pipeline_for_atomicity(limiter):
    mock_pipe = AsyncMock()
    mock_pipe.execute.return_value = [0, 1, 1, True]

    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    with patch.object(limiter, "_get_redis", return_value=mock_redis):
        await limiter.check("test:atomic", 10, 60)

    mock_redis.pipeline.assert_called_once()
    mock_pipe.zremrangebyscore.assert_called_once()
    mock_pipe.zadd.assert_called_once()
    mock_pipe.zcard.assert_called_once()
    mock_pipe.expire.assert_called_once()
    mock_pipe.execute.assert_called_once()
