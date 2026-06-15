"""Rate limiting configuration using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Default rate limits: 200/day, 50/hour, 5/minute
default_limits = [
    f"{settings.RATE_LIMIT_PER_MINUTE}/minute",
    f"{settings.RATE_LIMIT_PER_HOUR}/hour",
    f"{settings.RATE_LIMIT_PER_DAY}/day",
]

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=default_limits,  # type: ignore[arg-type]
    headers_enabled=False,
    enabled=settings.ENVIRONMENT != "test" and settings.RATE_LIMIT_ENABLED,
)
