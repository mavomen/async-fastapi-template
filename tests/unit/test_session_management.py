"""Tests for session management (Redis-backed token tracking)."""

from unittest.mock import AsyncMock

import pytest

from app.api.deps import get_current_user, get_db
from app.core.jwt_blacklist import (
    SessionCreatePayload,
    get_session,
    list_active_sessions,
    revoke_all_user_sessions,
    revoke_session,
    store_session,
)
from app.main import app

_JTI = "550e8400-e29b-41d4-a716-446655440000"
_USER_ID = 1


@pytest.fixture(autouse=True)
def _override_auth(mocker):
    fake_user = mocker.MagicMock()
    fake_user.id = _USER_ID
    fake_user.tenant_id = 2
    fake_user.email = "test@example.com"
    fake_user.is_active = True

    async def _fake_get_current_user():
        return fake_user

    async def _fake_get_db():
        return AsyncMock()

    app.dependency_overrides[get_current_user] = _fake_get_current_user
    app.dependency_overrides[get_db] = _fake_get_db
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


class TestStoreSession:
    @pytest.mark.asyncio
    async def test_store_session_skips_when_disabled(self, mocker):
        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = False
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        redis_mock = AsyncMock()
        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=redis_mock)

        await store_session(
            _USER_ID,
            SessionCreatePayload(
                jti=_JTI,
                token_type="access",
                ip="1.2.3.4",
                user_agent="test-agent",
                iat=1000,
                exp=9999999999,
            ),
        )
        redis_mock.zadd.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_session_calls_redis(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.zadd.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.hset.return_value = 1

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        fake_settings.JWT_BLACKLIST_TTL = 86400

        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        await store_session(
            _USER_ID,
            SessionCreatePayload(
                jti=_JTI,
                token_type="access",
                ip="1.2.3.4",
                user_agent="test-agent",
                iat=1000,
                exp=9999999999,
            ),
        )
        mock_redis.zadd.assert_called_once()
        mock_redis.expire.assert_called()
        mock_redis.hset.assert_called_once()


class TestListActiveSessions:
    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self, mocker):
        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = False
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        sessions = await list_active_sessions(_USER_ID)
        assert sessions == []

    @pytest.mark.asyncio
    async def test_returns_active_sessions(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.zrevrange.return_value = [_JTI]
        mock_redis.hgetall.return_value = {
            "jti": _JTI,
            "token_type": "access",
            "ip": "1.2.3.4",
            "user_agent": "test-agent",
            "created_at": "1000",
            "expires_at": "9999999999",
            "user_id": str(_USER_ID),
        }

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        sessions = await list_active_sessions(_USER_ID)
        assert len(sessions) == 1
        assert sessions[0]["jti"] == _JTI
        assert sessions[0]["token_type"] == "access"

    @pytest.mark.asyncio
    async def test_skips_expired_sessions(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.zrevrange.return_value = [_JTI]
        mock_redis.hgetall.return_value = {
            "jti": _JTI,
            "token_type": "access",
            "ip": "1.2.3.4",
            "user_agent": "test-agent",
            "created_at": "1",
            "expires_at": "1",
            "user_id": str(_USER_ID),
        }
        mock_redis.zrem.return_value = 1
        mock_redis.delete.return_value = 1

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        sessions = await list_active_sessions(_USER_ID)
        assert sessions == []
        mock_redis.zrem.assert_called_once()
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_sessions_without_metadata(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.zrevrange.return_value = [_JTI]
        mock_redis.hgetall.return_value = {}

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        sessions = await list_active_sessions(_USER_ID)
        assert sessions == []


class TestGetSession:
    @pytest.mark.asyncio
    async def test_get_session_returns_metadata(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {
            "jti": _JTI,
            "token_type": "access",
            "ip": "1.2.3.4",
            "user_agent": "test-agent",
            "created_at": "1000",
            "expires_at": "9999999999",
            "user_id": str(_USER_ID),
        }
        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)

        meta = await get_session(_USER_ID, _JTI)
        assert meta is not None
        assert meta["jti"] == _JTI

    @pytest.mark.asyncio
    async def test_get_session_returns_none_for_unknown(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}
        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)

        meta = await get_session(_USER_ID, "unknown-jti")
        assert meta is None


class TestRevokeSession:
    @pytest.mark.asyncio
    async def test_revoke_session_removes_and_blacklists(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.zrem.return_value = 1
        mock_redis.delete.return_value = 1
        mock_redis.sadd.return_value = 1
        mock_redis.expire.return_value = True

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        fake_settings.JWT_BLACKLIST_TTL = 86400

        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        await revoke_session(_USER_ID, _JTI, 9999999999)
        mock_redis.zrem.assert_called_once()
        mock_redis.delete.assert_called_once()
        mock_redis.sadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_session_skips_when_disabled(self, mocker):
        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = False
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        redis_mock = AsyncMock()
        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=redis_mock)

        await revoke_session(_USER_ID, _JTI, 9999999999)
        redis_mock.zrem.assert_not_called()


class TestRevokeAllUserSessions:
    @pytest.mark.asyncio
    async def test_revokes_all_sessions(self, mocker):
        mock_redis = AsyncMock()
        mock_redis.zrevrange.return_value = [_JTI, "jti-2"]
        mock_redis.hgetall.return_value = {
            "jti": _JTI,
            "token_type": "access",
            "ip": "1.2.3.4",
            "user_agent": "test-agent",
            "created_at": "1000",
            "expires_at": "9999999999",
            "user_id": str(_USER_ID),
        }
        mock_redis.delete.return_value = 1
        mock_redis.sadd.return_value = 1
        mock_redis.setex.return_value = True
        mock_redis.expire.return_value = True

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        fake_settings.JWT_BLACKLIST_TTL = 86400

        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        count = await revoke_all_user_sessions(_USER_ID)
        assert count == 2
        assert mock_redis.delete.call_count >= 2

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self, mocker):
        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = False
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        count = await revoke_all_user_sessions(_USER_ID)
        assert count == 0


class TestSessionEndpoints:
    def test_get_sessions(self, client, mocker):
        mock_redis = AsyncMock()
        mock_redis.zrevrange.return_value = [_JTI]
        mock_redis.hgetall.return_value = {
            "jti": _JTI,
            "token_type": "access",
            "ip": "1.2.3.4",
            "user_agent": "test-agent",
            "created_at": "1000",
            "expires_at": "9999999999",
            "user_id": "1",
        }

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        fake_settings.JWT_BLACKLIST_TTL = 86400

        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        resp = client.get("/api/v1/auth/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["jti"] == _JTI

    def test_revoke_session_endpoint(self, client, mocker):
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {
            "jti": _JTI,
            "token_type": "access",
            "ip": "1.2.3.4",
            "user_agent": "test-agent",
            "created_at": "1000",
            "expires_at": "9999999999",
            "user_id": "1",
        }
        mock_redis.zrem.return_value = 1
        mock_redis.delete.return_value = 1
        mock_redis.sadd.return_value = 1
        mock_redis.expire.return_value = True

        fake_settings = mocker.MagicMock()
        fake_settings.JWT_BLACKLIST_ENABLED = True
        fake_settings.JWT_BLACKLIST_TTL = 86400

        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)
        mocker.patch("app.core.jwt_blacklist.settings", fake_settings)

        resp = client.post(
            "/api/v1/auth/sessions/revoke",
            json={"jti": _JTI},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detail"] == "Session revoked"

    def test_revoke_session_not_found(self, client, mocker):
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}

        mocker.patch("app.core.jwt_blacklist.cache.get_redis", return_value=mock_redis)

        resp = client.post(
            "/api/v1/auth/sessions/revoke",
            json={"jti": "unknown-jti"},
        )
        assert resp.status_code == 404
