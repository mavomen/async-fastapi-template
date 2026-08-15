"""Decorators for per-route rate limiting.

Usage:
    @router.get("/resource")
    @rate_limit(times=10, seconds=30)
    async def resource():
        ...
"""

from typing import Any

RATE_LIMIT_CONFIG_ATTR = "_rate_limit_config"


def rate_limit(times: int = 5, seconds: int = 60) -> Any:
    """Mark a route handler with a custom rate limit.

    The middleware reads this metadata and applies the limit instead
    of the tier default.
    """

    def decorator(func: Any) -> Any:
        setattr(func, RATE_LIMIT_CONFIG_ATTR, (times, seconds))
        return func

    return decorator
