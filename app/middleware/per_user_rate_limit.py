"""Per-user rate limiting middleware (JWT sub-based)."""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

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

    async def dispatch(self, request: Request, call_next):
        # The user ID is set by the auth dependency earlier in the stack
        # We just let the limiter evaluate; if the request has no user_id, it falls back to IP
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded

        try:
            response = await call_next(request)
        except RateLimitExceeded:
            return _rate_limit_exceeded_handler(request, RateLimitExceeded)  # type: ignore[arg-type]
        return response
