"""OAuth2 service with Redis-backed state store."""

import logging
from typing import Any

from app.auth.oauth2 import OAUTH_STATE_KEY_PREFIX
from app.core.cache import cache
from app.core.config import settings

logger = logging.getLogger("app.oauth2")


async def store_oauth_state(state: str, data: dict[str, Any]) -> None:
    """Store OAuth state in Redis with TTL."""
    key = f"{OAUTH_STATE_KEY_PREFIX}{state}"
    await cache.set(key, data, ttl=settings.OAUTH_STATE_EXPIRE_SECONDS)


async def consume_oauth_state(state: str) -> dict[str, Any] | None:
    """Retrieve and delete OAuth state from Redis.

    Returns the stored data dict, or None if state is invalid/expired.
    This is a consume operation — the state is deleted after retrieval
    to prevent replay attacks.
    """
    key = f"{OAUTH_STATE_KEY_PREFIX}{state}"
    data_raw = await cache.get(key)
    if data_raw is None:
        return None
    await cache.delete(key)
    return data_raw  # type: ignore[no-any-return]
