"""Redis-backed sliding-window rate limiter."""

import time
import uuid
from dataclasses import dataclass

import redis.asyncio as aioredis

from app.core.cache import RedisCache, cache


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset: int


class RedisSlidingWindowLimiter:
    def __init__(self, cache_instance: RedisCache | None = None) -> None:
        self._cache = cache_instance or cache

    def _get_redis(self) -> aioredis.Redis:
        return self._cache.get_redis()

    async def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        window_start = now - window_seconds
        member = str(uuid.uuid4())

        pipe = self._get_redis().pipeline()
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()

        count: int = results[2]
        allowed = count <= limit
        remaining = max(0, limit - count)
        reset = int(time.time() - (now - window_start) + window_seconds)
        return RateLimitResult(allowed=allowed, remaining=remaining, reset=reset)


limiter = RedisSlidingWindowLimiter()
