"""Tests for auth audit event logging."""

from unittest.mock import AsyncMock

import pytest

from app.services.auth_audit import log_auth_event


class TestLogAuthEvent:
    @pytest.mark.asyncio
    async def test_log_login_success(self):
        db = AsyncMock()
        entry = await log_auth_event(
            db,
            event_type="login_success",
            user_id=1,
            tenant_id=2,
            ip_address="203.0.113.5",
            user_agent="TestAgent/1.0",
        )
        assert entry.event_type == "login_success"
        assert entry.user_id == 1
        assert entry.tenant_id == 2

    @pytest.mark.asyncio
    async def test_log_login_failure(self):
        db = AsyncMock()
        entry = await log_auth_event(
            db,
            event_type="login_failure",
            ip_address="203.0.113.5",
        )
        assert entry.event_type == "login_failure"
        assert entry.ip_address == "203.0.113.5"

    @pytest.mark.asyncio
    async def test_log_account_locked(self):
        db = AsyncMock()
        entry = await log_auth_event(
            db,
            event_type="account_locked",
            user_id=1,
            details={"locked_until": "2026-07-01T12:00:00", "failed_attempts": 5},
        )
        assert entry.event_type == "account_locked"
        assert entry.details is not None

    @pytest.mark.asyncio
    async def test_log_token_refresh(self):
        db = AsyncMock()
        entry = await log_auth_event(
            db,
            event_type="token_refresh",
            user_id=1,
        )
        assert entry.event_type == "token_refresh"

    @pytest.mark.asyncio
    async def test_raises_on_invalid_event_type(self):
        db = AsyncMock()
        with pytest.raises(ValueError, match="Invalid auth event type"):
            await log_auth_event(db, event_type="invalid_event")
