"""User-related GraphQL subscription for real-time events."""

import asyncio
from collections.abc import AsyncGenerator

import strawberry
from strawberry.types import Info

from app.core.config import settings
from app.events.base import Event, EventBus


def _get_event_bus() -> EventBus:
    """Return the configured event bus instance."""
    if settings.EVENT_BUS_BACKEND == "kafka":
        from app.events.kafka_bus import KafkaEventBus

        return KafkaEventBus(bootstrap_servers=settings.EVENT_BUS_KAFKA_SERVERS)
    from app.events.redis_streams import RedisStreamsEventBus

    redis_url = settings.EVENT_BUS_REDIS_URL or settings.REDIS_URL
    return RedisStreamsEventBus(redis_url=redis_url)


@strawberry.type
class UserSubscription:
    @strawberry.subscription(description="Receive a welcome message when a user logs in.")
    async def user_logged_in(self, _info: Info, user_id: int) -> AsyncGenerator[str, None]:
        bus = _get_event_bus()
        await bus.connect()

        async def handler(event: Event):
            yield f"User {user_id} logged in. Event: {event.event_type}"

        await bus.subscribe("user.logged_in", handler)
        try:
            while True:
                await asyncio.sleep(1)
        finally:
            await bus.unsubscribe("user.logged_in", handler)
            # Note: disconnect is tricky because the bus might be shared; for demo, we skip.
