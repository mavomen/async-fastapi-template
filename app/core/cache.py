"""Redis cache client wrapper providing async operations."""

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.metrics import cache_hits_total, cache_misses_total


class RedisCache:
    """Async Redis cache client with JSON serialization."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Initialize the Redis connection pool."""

    async def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def get(self, key: str) -> Any | None:
        """Retrieve a value from cache, deserializing from JSON."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        value = await self._redis.get(key)
        if value is None:
            cache_misses_total.inc()
            return None
        cache_hits_total.inc()
        return json.loads(value)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Set a value in cache with optional TTL (in seconds)."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        serialized = json.dumps(value, default=str)
        if ttl:
            await self._redis.setex(key, ttl, serialized)
        else:
            await self._redis.set(key, serialized)

    async def delete(self, key: str) -> None:
        """Remove a key from cache."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        return await self._redis.exists(key) > 0

    async def flush(self) -> None:
        """Clear all keys in the current database."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        await self._redis.flushdb()

    # self._redis = aioredis.from_url(  # type: ignore[attr-defined]
    #     settings.REDIS_URL,
    #     encoding="utf-8",
    #     decode_responses=True,
    # )


cache = RedisCache()
