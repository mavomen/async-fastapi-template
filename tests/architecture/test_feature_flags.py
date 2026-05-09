"""Tests for feature-flag overrides."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.feature_flags import is_feature_enabled


@pytest.mark.asyncio
async def test_env_var_override_true(monkeypatch):
    monkeypatch.setenv("FEATURE_WEBAUTHN", "true")
    with patch("app.core.feature_flags.cache.get", AsyncMock(return_value=None)):
        assert await is_feature_enabled("webauthn") is True


@pytest.mark.asyncio
async def test_env_var_override_false(monkeypatch):
    monkeypatch.setenv("FEATURE_WEBAUTHN", "false")
    with patch("app.core.feature_flags.cache.get", AsyncMock(return_value=None)):
        assert await is_feature_enabled("webauthn") is False


@pytest.mark.asyncio
async def test_cache_override():
    with patch("app.core.feature_flags.cache.get", AsyncMock(return_value=True)):
        assert await is_feature_enabled("webauthn") is True
