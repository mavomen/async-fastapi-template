"""Cover feature-flag branches (cache miss and unknown flags)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.feature_flags import is_feature_enabled


@pytest.mark.asyncio
async def test_unknown_feature_disabled():
    with patch("app.core.feature_flags.cache.get", AsyncMock(return_value=None)):
        assert await is_feature_enabled("unknown_feature") is False


@pytest.mark.asyncio
async def test_cache_returns_false():
    with patch("app.core.feature_flags.cache.get", AsyncMock(return_value=False)):
        assert await is_feature_enabled("webauthn") is False
