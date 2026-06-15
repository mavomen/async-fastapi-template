"""Cache warming and cache-aside pattern utilities."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.cache import cache


async def cache_aside(
    key: str,
    fetch_func: Callable[[], Awaitable[Any]],
    ttl: int = 300,
) -> Any:
    """
    Cache-aside pattern: return cached value if present,
    otherwise call `fetch_func`, store result in cache, and return it.
    """
    cached = await cache.get(key)
    if cached is not None:
        return cached
    data = await fetch_func()
    await cache.set(key, data, ttl=ttl)
    return data


async def warm_cache(
    keys_and_fetchers: dict[str, Callable[[], Awaitable[Any]]],
    ttl: int = 300,
) -> None:
    """Warm multiple cache keys concurrently."""
    await asyncio.gather(
        *[cache_aside(key, fetch_func, ttl=ttl) for key, fetch_func in keys_and_fetchers.items()]
    )
