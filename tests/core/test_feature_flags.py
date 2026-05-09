"""Tests for feature flag system."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.feature_flags import is_feature_enabled


@pytest.mark.asyncio
async def test_known_feature_enabled():
    with patch("app.core.feature_flags.cache.get", AsyncMock(return_value=None)):
        assert await is_feature_enabled("webauthn") is True


@pytest.mark.asyncio
async def test_unknown_feature_disabled():
    with patch("app.core.feature_flags.cache.get", AsyncMock(return_value=None)):
        assert await is_feature_enabled("nonexistent") is False
