"""Utility functions for cache invalidation."""

from app.core.cache import cache


async def invalidate_by_prefix(prefix: str) -> None:
    """Delete all cache keys matching a given prefix.
    Uses Redis SCAN to avoid blocking.
    """
    if cache._redis is None:
        raise RuntimeError("Cache not connected")
    # Note: This implementation assumes simple prefix matching; adjust for production.
    cursor = 0
    while True:
        cursor, keys = await cache._redis.scan(cursor, match=f"{prefix}*", count=100)
        if keys:
            await cache._redis.delete(*keys)
        if cursor == 0:
            break
