"""
Tests for brute-force login lockout.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import LockedOutException
from app.core.security import authenticate_user


class TestAuthenticateUser:
    @pytest.mark.asyncio
    async def test_successful_login_resets_attempts(self, mocker):
        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.hashed_password = "$2b$12$dummyhash"
        mock_user.failed_login_attempts = 3
        mock_user.locked_until = None
        mock_user.last_login_at = None

        mocker.patch("app.identity.crud.user.user.get_by_email", return_value=mock_user)
        mocker.patch("app.core.security.verify_password", return_value=True)

        result = await authenticate_user(AsyncMock(), email="test@test.com", password="pass")

        assert result is mock_user
        assert mock_user.failed_login_attempts == 0
        assert mock_user.locked_until is None
        assert mock_user.last_login_at is not None

    @pytest.mark.asyncio
    async def test_failed_login_increments_attempts(self, mocker):
        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.hashed_password = "$2b$12$dummyhash"
        mock_user.failed_login_attempts = 0
        mock_user.locked_until = None

        mocker.patch("app.identity.crud.user.user.get_by_email", return_value=mock_user)
        mocker.patch("app.core.security.verify_password", return_value=False)

        result = await authenticate_user(AsyncMock(), email="test@test.com", password="wrong")

        assert result is None
        assert mock_user.failed_login_attempts == 1

    @pytest.mark.asyncio
    async def test_locks_account_after_max_attempts(self, mocker):
        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.hashed_password = "$2b$12$dummyhash"
        mock_user.failed_login_attempts = 4
        mock_user.locked_until = None

        mocker.patch("app.identity.crud.user.user.get_by_email", return_value=mock_user)
        mocker.patch("app.core.security.verify_password", return_value=False)

        result = await authenticate_user(AsyncMock(), email="test@test.com", password="wrong")

        assert result is None
        assert mock_user.failed_login_attempts == 5
        assert mock_user.locked_until is not None

    @pytest.mark.asyncio
    async def test_raises_locked_exception_when_locked(self, mocker):
        future = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)

        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.hashed_password = "$2b$12$dummyhash"
        mock_user.failed_login_attempts = 5
        mock_user.locked_until = future

        mocker.patch("app.identity.crud.user.user.get_by_email", return_value=mock_user)

        with pytest.raises(LockedOutException):
            await authenticate_user(AsyncMock(), email="test@test.com", password="any")

    @pytest.mark.asyncio
    async def test_expired_lock_does_not_block(self, mocker):
        past = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)

        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.hashed_password = "$2b$12$dummyhash"
        mock_user.failed_login_attempts = 5
        mock_user.locked_until = past

        mocker.patch("app.identity.crud.user.user.get_by_email", return_value=mock_user)
        mocker.patch("app.core.security.verify_password", return_value=True)

        result = await authenticate_user(AsyncMock(), email="test@test.com", password="pass")

        assert result is mock_user
        assert mock_user.failed_login_attempts == 0
        assert mock_user.locked_until is None

    @pytest.mark.asyncio
    async def test_nonexistent_user_returns_none(self, mocker):
        mocker.patch("app.identity.crud.user.user.get_by_email", return_value=None)

        result = await authenticate_user(AsyncMock(), email="nobody@test.com", password="anything")
        assert result is None
