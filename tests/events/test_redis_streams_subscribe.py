"""Integration test for Redis Streams subscribe/unsubscribe."""

from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as aioredis

from app.events.base import Event
from app.events.redis_streams import RedisStreamsEventBus


@pytest.mark.asyncio
async def test_redis_subscribe_unsubscribe():
    with patch("app.events.redis_streams.aioredis.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock(
            side_effect=aioredis.ResponseError("BUSYGROUP")
        )
        mock_redis.xadd = AsyncMock()
        mock_redis.xreadgroup = AsyncMock()
        mock_redis.xack = AsyncMock()
        mock_redis.close = AsyncMock()
        mock_from_url.return_value = mock_redis

        bus = RedisStreamsEventBus(
            redis_url="redis://fake:6379", stream_name="test:events"
        )
        await bus.connect()

        received = []

        async def handler(e):
            received.append(e)

        await bus.subscribe("test", handler)
        assert len(bus._handlers.get("test", [])) == 1

        event = Event(event_type="test", payload={"msg": "hello"})
        await bus.publish(event)
        mock_redis.xadd.assert_called_once()

        await bus.unsubscribe("test", handler)
        assert "test" not in bus._handlers or len(bus._handlers.get("test", [])) == 0

        await bus.close()
