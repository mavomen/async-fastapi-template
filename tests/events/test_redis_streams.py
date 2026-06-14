"""Mocked integration test for Redis Streams event bus."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as aioredis

from app.events.base import Event


@pytest.fixture
def mock_redis():
    with patch("app.events.redis_streams.aioredis.from_url") as mock_from_url:
        mock_redis = AsyncMock()
        mock_redis.xgroup_create = AsyncMock(
            side_effect=aioredis.ResponseError("BUSYGROUP Consumer Group name already exists")
        )
        mock_redis.xadd = AsyncMock()
        mock_redis.xreadgroup = AsyncMock()
        mock_redis.xack = AsyncMock()
        mock_redis.close = AsyncMock()
        mock_from_url.return_value = mock_redis
        yield mock_redis


@pytest.mark.asyncio
async def test_redis_streams_publish_and_consume(mock_redis):
    """Publish an event using a mocked Redis client."""
    from app.events.redis_streams import RedisStreamsEventBus

    bus = RedisStreamsEventBus(redis_url="redis://fake:6379", stream_name="test:events")
    await bus.connect()

    event = Event(event_type="test", payload={"msg": "hello"})
    await bus.publish(event)

    mock_redis.xadd.assert_called_once()
    await bus.close()


@pytest.mark.asyncio
async def test_redis_streams_no_ack_on_handler_failure(mock_redis):
    """xack is NOT called when a handler raises an exception."""
    mock_redis.xreadgroup.side_effect = [
        [
            (
                "test:events",
                [
                    (
                        b"1620000000000-0",
                        {
                            "event": '{"event_type": "fail", "payload": {}, "id": "1", "timestamp": 0}'
                        },
                    ),
                ],
            )
        ],
        asyncio.CancelledError(),
    ]

    from app.events.redis_streams import RedisStreamsEventBus

    bus = RedisStreamsEventBus(redis_url="redis://fake:6379", stream_name="test:events")
    await bus.connect()

    fail_handler = AsyncMock(side_effect=ValueError("handler failed"))
    await bus.subscribe("fail", fail_handler)

    await bus._consume_loop()

    fail_handler.assert_awaited_once()
    mock_redis.xack.assert_not_called()
    await bus.close()
