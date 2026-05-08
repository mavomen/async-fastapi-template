"""Tests for cache invalidation utility."""

import pytest
from unittest.mock import patch, AsyncMock
from app.utils.cache_invalidation import invalidate_by_prefix


@pytest.mark.asyncio
async def test_invalidate_by_prefix():
    mock_redis = AsyncMock()
    mock_redis.scan.side_effect = [
        (0, ["prefix:a", "prefix:b"]),
    ]
    with patch("app.utils.cache_invalidation.cache._redis", mock_redis):
        await invalidate_by_prefix("prefix")
        mock_redis.delete.assert_called_once_with("prefix:a", "prefix:b")
