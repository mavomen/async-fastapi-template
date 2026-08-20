"""Tests for Redis-backed rate limit middleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.responses import Response

from app.core.exceptions import RateLimitException
from app.middleware.redis_rate_limit import (
    RedisRateLimitMiddleware,
    _get_identifier,
    _get_remote_address,
    _get_tier_config,
    _hash_key,
    _is_authenticated,
    _is_unlimited,
    _path_matches_any,
)

_DEV_SETTINGS = MagicMock(
    ENVIRONMENT="development",
    RATE_LIMIT_ENABLED=True,
    RATE_LIMIT_WINDOW_SECONDS=60,
    RATE_LIMIT_SENSITIVE=5,
    RATE_LIMIT_PUBLIC=20,
    RATE_LIMIT_AUTHENTICATED=100,
    RATE_LIMIT_ADMIN=300,
)
_TEST_SETTINGS = MagicMock(ENVIRONMENT="test", RATE_LIMIT_ENABLED=True)


class TestHelperFunctions:
    def test_is_unlimited_healthz(self):
        assert _is_unlimited("/healthz") is True
        assert _is_unlimited("/readyz") is True
        assert _is_unlimited("/metrics") is True

    def test_is_unlimited_other(self):
        assert _is_unlimited("/api/v1/auth/login") is False
        assert _is_unlimited("/admin") is False

    def test_path_matches_any(self):
        prefixes = {"/api/v1/auth/login", "/api/v1/auth/totp"}
        assert _path_matches_any("/api/v1/auth/login", prefixes) is True
        assert _path_matches_any("/api/v1/auth/totp/enable", prefixes) is True
        assert _path_matches_any("/api/v1/users", prefixes) is False

    def test_get_tier_config_admin(self):
        with patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS):
            tier, limit, window = _get_tier_config("/admin/users", authenticated=False)
        assert tier == "admin"
        assert limit == _DEV_SETTINGS.RATE_LIMIT_ADMIN
        assert window == _DEV_SETTINGS.RATE_LIMIT_WINDOW_SECONDS

    def test_get_tier_config_sensitive(self):
        with patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS):
            tier, limit, window = _get_tier_config("/api/v1/auth/login", authenticated=False)
        assert tier == "sensitive"
        assert limit == _DEV_SETTINGS.RATE_LIMIT_SENSITIVE

    def test_get_tier_config_public(self):
        with patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS):
            tier, limit, window = _get_tier_config("/api/v1/users", authenticated=False)
        assert tier == "public"
        assert limit == _DEV_SETTINGS.RATE_LIMIT_PUBLIC

    def test_get_tier_config_authenticated(self):
        with patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS):
            tier, limit, window = _get_tier_config("/api/v1/users", authenticated=True)
        assert tier == "authenticated"
        assert limit == _DEV_SETTINGS.RATE_LIMIT_AUTHENTICATED
        assert window == _DEV_SETTINGS.RATE_LIMIT_WINDOW_SECONDS

    def test_sensitive_overrides_authenticated(self):
        with patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS):
            tier, limit, window = _get_tier_config("/api/v1/auth/login", authenticated=True)
        assert tier == "sensitive"
        assert limit == _DEV_SETTINGS.RATE_LIMIT_SENSITIVE

    def test_admin_overrides_authenticated(self):
        with patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS):
            tier, limit, window = _get_tier_config("/admin/users", authenticated=True)
        assert tier == "admin"
        assert limit == _DEV_SETTINGS.RATE_LIMIT_ADMIN

    def test_hash_key_length(self):
        h = _hash_key("test")
        assert len(h) == 16

    def test_identifier_falls_back_to_ip(self):
        request = MagicMock()
        request.state = MagicMock(spec=[])
        request.client.host = "10.0.0.1"
        request.headers = {}
        ident = _get_identifier(request)
        assert ident == "10.0.0.1"

    def test_identifier_uses_user_id_when_present(self):
        request = MagicMock()
        request.state = MagicMock()
        request.state.user_id = "user-123"
        request.client.host = "10.0.0.1"
        request.headers = {}
        ident = _get_identifier(request)
        assert ident == "user-123"

    def test_is_authenticated_true(self):
        request = MagicMock()
        request.state = MagicMock()
        request.state.user_id = "user-123"
        assert _is_authenticated(request) is True

    def test_is_authenticated_false(self):
        request = MagicMock()
        request.state = MagicMock(spec=[])
        assert _is_authenticated(request) is False

    def test_get_remote_address_from_forwarded(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "203.0.113.5, 10.0.0.1"}
        addr = _get_remote_address(request)
        assert addr == "203.0.113.5"

    def test_get_remote_address_fallback(self):
        request = MagicMock()
        request.headers = {}
        request.client = None
        addr = _get_remote_address(request)
        assert addr == "127.0.0.1"


class TestRedisRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_skips_in_test_mode(self):
        request = MagicMock()
        call_next = AsyncMock(return_value=Response(status_code=200))
        middleware = RedisRateLimitMiddleware(app=None)

        with patch("app.middleware.redis_rate_limit.settings", _TEST_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_unlimited_path(self):
        request = MagicMock()
        request.url.path = "/healthz"
        call_next = AsyncMock(return_value=Response(status_code=200))
        middleware = RedisRateLimitMiddleware(app=None)

        with patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        call_next.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_injects_rate_limit_headers_public(self):
        request = MagicMock()
        request.url.path = "/api/v1/users"
        request.state = MagicMock(spec=[])
        request.client.host = "10.0.0.1"
        request.headers = {}
        request.app.routes = []
        call_next = AsyncMock(return_value=Response(status_code=200))
        middleware = RedisRateLimitMiddleware(app=None)

        with (
            patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS),
            patch(
                "app.middleware.redis_rate_limit.limiter.check",
                AsyncMock(return_value=MagicMock(allowed=True, remaining=15, reset=1234567890)),
            ),
        ):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "20"
        assert response.headers["X-RateLimit-Remaining"] == "15"
        assert response.headers["X-RateLimit-Reset"] == "1234567890"

    @pytest.mark.asyncio
    async def test_injects_rate_limit_headers_authenticated(self):
        request = MagicMock()
        request.url.path = "/api/v1/users"
        request.state = MagicMock()
        request.state.user_id = "user-42"
        request.client.host = "10.0.0.1"
        request.headers = {}
        request.app.routes = []
        call_next = AsyncMock(return_value=Response(status_code=200))
        middleware = RedisRateLimitMiddleware(app=None)

        with (
            patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS),
            patch(
                "app.middleware.redis_rate_limit.limiter.check",
                AsyncMock(return_value=MagicMock(allowed=True, remaining=95, reset=1234567890)),
            ),
        ):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Remaining"] == "95"

    @pytest.mark.asyncio
    async def test_returns_429_when_blocked_raises_exception(self):
        request = MagicMock()
        request.url.path = "/api/v1/auth/login"
        request.state = MagicMock(spec=[])
        request.client.host = "10.0.0.1"
        request.headers = {}
        request.app.routes = []
        call_next = AsyncMock()
        middleware = RedisRateLimitMiddleware(app=None)

        with (
            patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS),
            patch(
                "app.middleware.redis_rate_limit.limiter.check",
                AsyncMock(return_value=MagicMock(allowed=False, remaining=0, reset=1234567890)),
            ),
            patch("app.middleware.redis_rate_limit.rate_limit_blocked_total"),
        ):
            with pytest.raises(RateLimitException):
                await middleware.dispatch(request, call_next)

        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_sensitive_tier_used_for_auth_endpoints(self):
        request = MagicMock()
        request.url.path = "/api/v1/auth/login"
        request.state = MagicMock(spec=[])
        request.client.host = "10.0.0.1"
        request.headers = {}
        request.app.routes = []
        call_next = AsyncMock(return_value=Response(status_code=200))
        middleware = RedisRateLimitMiddleware(app=None)

        with (
            patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS),
            patch(
                "app.middleware.redis_rate_limit.limiter.check",
                AsyncMock(return_value=MagicMock(allowed=True, remaining=3, reset=1234567890)),
            ),
        ):
            response = await middleware.dispatch(request, call_next)

        assert response.headers["X-RateLimit-Limit"] == "5"

    @pytest.mark.asyncio
    async def test_admin_tier_used_for_admin_paths(self):
        request = MagicMock()
        request.url.path = "/admin/dashboard"
        request.state = MagicMock(spec=[])
        request.client.host = "10.0.0.1"
        request.headers = {}
        request.app.routes = []
        call_next = AsyncMock(return_value=Response(status_code=200))
        middleware = RedisRateLimitMiddleware(app=None)

        with (
            patch("app.middleware.redis_rate_limit.settings", _DEV_SETTINGS),
            patch(
                "app.middleware.redis_rate_limit.limiter.check",
                AsyncMock(return_value=MagicMock(allowed=True, remaining=290, reset=1234567890)),
            ),
        ):
            response = await middleware.dispatch(request, call_next)

        assert response.headers["X-RateLimit-Limit"] == "300"
