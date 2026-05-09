"""Test the feature-flag cache-hit branch."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.feature_flags import is_feature_enabled


@pytest.mark.asyncio
async def test_feature_flag_cached():
    with patch("app.core.feature_flags.cache.get", AsyncMock(return_value=False)):
        assert await is_feature_enabled("webauthn") is False
