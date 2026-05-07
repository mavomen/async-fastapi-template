"""Utility for batch Redis operations using pipelines."""

import json
from typing import Any

import redis.asyncio as aioredis


async def batch_set(
    redis: aioredis.Redis,
    data: dict[str, Any],
    ttl: int | None = None,
) -> None:
    """Pipeline multiple set operations."""
    pipeline = redis.pipeline()
    for key, value in data.items():
        serialized = json.dumps(value, default=str)
        if ttl:
            pipeline.setex(key, ttl, serialized)
        else:
            pipeline.set(key, serialized)
    await pipeline.execute()


async def batch_get(redis: aioredis.Redis, keys: list[str]) -> dict[str, Any | None]:
    """Pipeline multiple get operations."""
    pipeline = redis.pipeline()
    for key in keys:
        pipeline.get(key)
    results = await pipeline.execute()
    return {
        key: json.loads(val) if val else None
        for key, val in zip(keys, results)
    }
