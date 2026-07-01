"""Redis cache client wrapper providing async operations."""

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.metrics import cache_hits_total, cache_misses_total


class RedisCache:
    """Async Redis cache client with JSON serialization."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Initialize the Redis connection pool."""
        self._redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

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
        n = await self._redis.exists(key)
        return bool(n > 0)

    async def ping(self) -> bool:
        """Check if the Redis connection is alive."""
        if self._redis is None:
            return False
        try:
            await self._redis.ping()  # type: ignore[misc]
            return True
        except Exception:
            return False

    async def zadd(self, key: str, mapping: dict[str | bytes, float]) -> int:
        """Add members with scores to a sorted set. Returns number of new elements added."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        return await self._redis.zadd(key, mapping)  # type: ignore[no-any-return, type-var]

    async def zrange(
        self, key: str, start: int = 0, end: int = -1, desc: bool = False, withscores: bool = False
    ) -> list[Any]:
        """Return a range of members from a sorted set by index."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        return await self._redis.zrange(key, start, end, desc=desc, withscores=withscores)  # type: ignore[no-any-return]

    async def zrevrange(
        self, key: str, start: int = 0, end: int = -1, withscores: bool = False
    ) -> list[Any]:
        """Return members of a sorted set in reverse order by score."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        return await self._redis.zrevrange(key, start, end, withscores=withscores)  # type: ignore[no-any-return]

    async def zincrby(self, key: str, amount: float = 1, member: str = "") -> float:
        """Increment the score of a member in a sorted set."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        return await self._redis.zincrby(key, amount, member)  # type: ignore[no-any-return]

    async def zcard(self, key: str) -> int:
        """Return the cardinality (number of members) of a sorted set."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        return await self._redis.zcard(key)  # type: ignore[no-any-return]

    async def zrem(self, key: str, *members: str) -> int:
        """Remove members from a sorted set. Returns number of removed members."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        return await self._redis.zrem(key, *members)  # type: ignore[no-any-return]

    def get_redis(self) -> aioredis.Redis:
        """Return the underlying Redis client for advanced operations."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        return self._redis

    async def flush(self) -> None:
        """Clear all keys in the current database."""
        if self._redis is None:
            raise RuntimeError("RedisCache is not connected")
        await self._redis.flushdb()


cache = RedisCache()
