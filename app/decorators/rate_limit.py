"""Decorators for per-route rate limiting."""

from typing import Any

from app.core.rate_limit import limiter


def rate_limit(times: int = 5, seconds: int = 60) -> Any:
    """Shortcut to apply a custom rate limit string.

    Usage:
        @router.get("/resource")
        @rate_limit(times=10, seconds=30)
        async def resource():
            ...
    """
    return limiter.limit(f"{times}/{seconds}seconds")
