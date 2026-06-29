"""
Tests for JWT blacklist / revocation.
"""

from unittest.mock import AsyncMock

import pytest

from app.core.jwt_blacklist import blacklist_token, is_token_blacklisted, revoke_all_user_tokens
from app.core.security import _make_jwt_payload, create_access_token


class TestJWTTokenClaims:
    def test_access_token_has_jti(self):
        payload = _make_jwt_payload(subject="1", expires_delta=None)
        assert "jti" in payload
        assert len(payload["jti"]) == 36
        assert "iat" in payload
        assert "sub" in payload
        assert payload["sub"] == "1"
        assert "purpose" not in payload

    def test_refresh_token_has_purpose(self):
        from datetime import timedelta

        payload = _make_jwt_payload(subject="1", expires_delta=timedelta(days=7), purpose="refresh")
        assert payload["purpose"] == "refresh"

    def test_create_access_token_returns_jwt_with_three_parts(self):
        token = create_access_token(subject="1")
        parts = token.split(".")
        assert len(parts) == 3


class TestJWTBlacklist:
    @pytest.mark.asyncio
    async def test_blacklist_disabled_when_flag_off(self, mocker):
        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = False
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)
        result = await is_token_blacklisted(1, "some-jti")
        assert result is False

    @pytest.mark.asyncio
    async def test_blacklist_and_check_token(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.sadd.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.smembers.return_value = {"test-jti:9999999999"}

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        fake_settings.JWT_BLACKLIST_TTL = 86400

        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        await blacklist_token(1, "test-jti", 9999999999)
        mock_redis.sadd.assert_called_once()
        mock_redis.expire.assert_called_once()

        blacklisted = await is_token_blacklisted(1, "test-jti")
        assert blacklisted is True

    @pytest.mark.asyncio
    async def test_expired_token_not_blacklisted(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.smembers.return_value = {"expired-jti:1"}

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True

        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        blacklisted = await is_token_blacklisted(1, "expired-jti")
        assert blacklisted is False

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.scard.return_value = 5
        mock_redis.delete.return_value = 1
        mock_redis.setex.return_value = True

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        fake_settings.JWT_BLACKLIST_TTL = 86400

        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        count = await revoke_all_user_tokens(1)
        assert count == 5
        mock_redis.scard.assert_called_once()
        mock_redis.delete.assert_called_once()
        mock_redis.setex.assert_called_once()
