"""Per-user rate limiting middleware (JWT sub-based)."""

from collections.abc import Awaitable, Callable

from fastapi import Request
from slowapi import Limiter
from slowapi.middleware import _find_route_handler, _should_exempt, async_check_limits
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings

per_user_limiter = Limiter(
    key_func=lambda request: (
        request.state.user_id if hasattr(request.state, "user_id") else get_remote_address(request)
    ),
    default_limits=[
        f"{settings.RATE_LIMIT_PER_MINUTE}/minute",
    ],
    headers_enabled=True,
)


class PerUserRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limits scoped to authenticated user ID."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if settings.ENVIRONMENT == "test":
            return await call_next(request)
        if not per_user_limiter.enabled:
            return await call_next(request)

        handler = _find_route_handler(request.app.routes, request.scope)
        if _should_exempt(per_user_limiter, handler):
            return await call_next(request)

        error_response, should_inject_headers = await async_check_limits(
            per_user_limiter, request, handler, request.app
        )
        if error_response is not None:
            return error_response

        response = await call_next(request)
        if should_inject_headers:
            response = per_user_limiter._inject_headers(response, request.state.view_rate_limit)
        return response
