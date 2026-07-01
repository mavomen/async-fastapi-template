"""Tests for passwordless magic link tokens and flow."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import create_magic_link_token, decode_magic_link_token


class TestMagicLinkTokens:
    def test_create_token_returns_valid_jwt(self):
        token = create_magic_link_token("user@example.com")
        parts = token.split(".")
        assert len(parts) == 3

        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
        assert payload["sub"] == "user@example.com"
        assert payload["purpose"] == "magic_link"
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_valid_token(self):
        token = create_magic_link_token("test@test.com")
        payload = decode_magic_link_token(token)
        assert payload["sub"] == "test@test.com"
        assert payload["purpose"] == "magic_link"
        assert "jti" in payload

    def test_decode_expired_token_raises(self):
        expire = datetime.now(UTC) - timedelta(hours=1)
        token = jwt.encode(
            {"exp": expire, "sub": "old@test.com", "purpose": "magic_link", "jti": "abc"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(Exception, match="Invalid or expired magic link"):
            decode_magic_link_token(token)

    def test_decode_wrong_purpose_raises(self):
        token = jwt.encode(
            {"exp": datetime.now(UTC) + timedelta(hours=1), "sub": "test@test.com", "purpose": "login"},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(Exception, match="Invalid token purpose"):
            decode_magic_link_token(token)

    def test_decode_tampered_token_raises(self):
        with pytest.raises(Exception, match="Invalid or expired magic link"):
            decode_magic_link_token("eyJfake.eyJ0eXAiOiJKV1QifQ.fake")


class TestMagicLinkVerify:
    @pytest.mark.asyncio
    async def test_verify_with_existing_user_returns_tokens(self, mocker):
        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.tenant_id = 2
        mock_user.is_verified = True
        mock_user.email = "user@example.com"

        mocker.patch("app.crud.user.user.get_by_email", return_value=mock_user)

        db = AsyncMock()
        from app.api.endpoints.auth import verify_magic_link

        request = AsyncMock()
        request.client = None
        request.headers = {}

        token = create_magic_link_token("user@example.com")
        result = await verify_magic_link(request=request, token=token, db=db)

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_verify_auto_registers_new_user(self, mocker):
        mocker.patch("app.crud.user.user.get_by_email", return_value=None)

        db = AsyncMock()
        db.refresh = AsyncMock()

        from app.api.endpoints.auth import verify_magic_link

        request = AsyncMock()
        request.client = None
        request.headers = {}

        token = create_magic_link_token("newuser@example.com")

        result = await verify_magic_link(request=request, token=token, db=db)

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_verify_with_unverified_user_marks_verified(self, mocker):
        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.tenant_id = 2
        mock_user.is_verified = False
        mock_user.email = "unverified@example.com"

        mocker.patch("app.crud.user.user.get_by_email", return_value=mock_user)

        db = AsyncMock()

        from app.api.endpoints.auth import verify_magic_link

        request = AsyncMock()
        request.client = None
        request.headers = {}

        token = create_magic_link_token("unverified@example.com")

        result = await verify_magic_link(request=request, token=token, db=db)

        assert "access_token" in result
        assert mock_user.is_verified is True

    @pytest.mark.asyncio
    async def test_verify_invalid_token_raises(self):
        from app.core.security import decode_magic_link_token

        with pytest.raises(Exception, match="Invalid or expired magic link"):
            decode_magic_link_token("invalidtoken")

    @pytest.mark.asyncio
    async def test_verify_with_registration_disabled_raises(self, mocker):
        mocker.patch("app.crud.user.user.get_by_email", return_value=None)

        fake_settings = mocker.MagicMock()
        fake_settings.MAGIC_LINK_ALLOW_REGISTRATION = False
        fake_settings.ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        fake_settings.REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS
        fake_settings.SECRET_KEY = settings.SECRET_KEY
        fake_settings.ALGORITHM = settings.ALGORITHM
        fake_settings.JWT_BLACKLIST_ENABLED = settings.JWT_BLACKLIST_ENABLED
        mocker.patch("app.core.config.settings", fake_settings)

        from app.api.endpoints.auth import verify_magic_link

        request = AsyncMock()
        request.client = None
        request.headers = {}

        db = AsyncMock()
        token = create_magic_link_token("unknown@example.com")

        with pytest.raises(Exception, match="Registration via magic link is disabled"):
            await verify_magic_link(request=request, token=token, db=db)
