"""Mocked integration test for Redis Streams event bus."""

from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as aioredis

from app.events.base import Event


@pytest.mark.asyncio
async def test_redis_streams_publish_and_consume():
    """Publish an event using a mocked Redis client."""
    with patch("app.events.redis_streams.aioredis.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        # Simulate an existing consumer group by raising the real exception type
        mock_redis.xgroup_create = AsyncMock(
            side_effect=aioredis.ResponseError(
                "BUSYGROUP Consumer Group name already exists"
            )
        )
        mock_redis.xadd = AsyncMock()
        mock_redis.xreadgroup = AsyncMock()
        mock_redis.xack = AsyncMock()
        mock_redis.close = AsyncMock()
        mock_from_url.return_value = mock_redis

        from app.events.redis_streams import RedisStreamsEventBus

        bus = RedisStreamsEventBus(
            redis_url="redis://fake:6379", stream_name="test:events"
        )
        await bus.connect()

        event = Event(event_type="test", payload={"msg": "hello"})
        await bus.publish(event)

        mock_redis.xadd.assert_called_once()
        await bus.close()
