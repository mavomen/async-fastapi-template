"""Redis-backed sliding-window rate limit middleware.

Tier-based rate limiting with four levels: sensitive, authenticated,
public, and admin. Uses Redis sorted sets for sliding-window counting.
"""

import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.exceptions import RateLimitException
from app.core.metrics import rate_limit_blocked_total, rate_limit_remaining
from app.core.rate_limiter import limiter

UNLIMITED_PATHS = {"/healthz", "/readyz", "/metrics"}
SENSITIVE_PREFIXES = {
    f"{settings.API_V1_STR}/auth/login",
    f"{settings.API_V1_STR}/auth/register",
    f"{settings.API_V1_STR}/auth/oauth",
    f"{settings.API_V1_STR}/auth/totp",
    f"{settings.API_V1_STR}/auth/magic-link",
}
ADMIN_PREFIX = "/admin"


def _get_remote_address(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def _get_identifier(request: Request) -> str:
    user_id: str | None = getattr(request.state, "user_id", None)
    if user_id is not None:
        return user_id
    return _get_remote_address(request)


def _path_matches_any(path: str, prefixes: set[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _is_authenticated(request: Request) -> bool:
    return getattr(request.state, "user_id", None) is not None


def _get_tier_config(path: str, authenticated: bool) -> tuple[str, int, int]:
    if path.startswith(ADMIN_PREFIX):
        return ("admin", settings.RATE_LIMIT_ADMIN, settings.RATE_LIMIT_WINDOW_SECONDS)
    if _path_matches_any(path, SENSITIVE_PREFIXES):
        return ("sensitive", settings.RATE_LIMIT_SENSITIVE, settings.RATE_LIMIT_WINDOW_SECONDS)
    if authenticated:
        return (
            "authenticated",
            settings.RATE_LIMIT_AUTHENTICATED,
            settings.RATE_LIMIT_WINDOW_SECONDS,
        )
    return ("public", settings.RATE_LIMIT_PUBLIC, settings.RATE_LIMIT_WINDOW_SECONDS)


def _is_unlimited(path: str) -> bool:
    return path in UNLIMITED_PATHS


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if settings.ENVIRONMENT == "test" or not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path
        if _is_unlimited(path):
            return await call_next(request)

        identifier = _get_identifier(request)
        authenticated = _is_authenticated(request)

        tier_name, tier_limit, tier_window = _get_tier_config(path, authenticated)
        handler = self._find_handler(request)

        if handler is not None:
            custom_config: tuple[int, int] | None = getattr(handler, "_rate_limit_config", None)
            if custom_config is not None:
                custom_limit, custom_window = custom_config
                key = f"rate_limit:custom:{_hash_key(identifier)}:{_hash_key(path)}"
                limit = custom_limit
                window = custom_window
            else:
                key = f"rate_limit:{tier_name}:{_hash_key(identifier)}"
                limit = tier_limit
                window = tier_window
        else:
            key = f"rate_limit:{tier_name}:{_hash_key(identifier)}"
            limit = tier_limit
            window = tier_window

        result = await limiter.check(key, limit, window)

        if not result.allowed:
            rate_limit_blocked_total.labels(tier=tier_name, endpoint=path).inc()
            raise RateLimitException

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset)
        rate_limit_remaining.labels(tier=tier_name).set(result.remaining)
        return response

    def _find_handler(self, request: Request) -> Any:
        for route in request.app.routes:
            if hasattr(route, "methods") and request.method in route.methods:
                match, _ = route.matches(request.scope)
                if match:
                    return route.endpoint
        return None
