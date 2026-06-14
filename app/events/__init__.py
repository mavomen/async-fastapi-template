"""Event bus singleton factory — lazily initialises and reuses one bus instance."""

import asyncio

from app.core.config import settings
from app.events.base import EventBus

_state: dict[str, EventBus | None] = {"bus": None}
_event_bus_lock = asyncio.Lock()


async def get_event_bus() -> EventBus:
    """Return the single event-bus instance, creating and connecting it once."""
    existing = _state["bus"]
    if existing is not None:
        return existing
    async with _event_bus_lock:
        existing = _state["bus"]
        if existing is not None:
            return existing
        instance: EventBus
        if settings.EVENT_BUS_BACKEND == "kafka":
            from app.events.kafka_bus import KafkaEventBus

            instance = KafkaEventBus(bootstrap_servers=settings.EVENT_BUS_KAFKA_SERVERS)
        else:
            from app.events.redis_streams import RedisStreamsEventBus

            redis_url = settings.EVENT_BUS_REDIS_URL or settings.REDIS_URL
            instance = RedisStreamsEventBus(redis_url=redis_url)
        await instance.connect()
        _state["bus"] = instance
        return instance
