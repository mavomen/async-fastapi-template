"""User-related GraphQL subscription for real-time events."""

import asyncio
from collections.abc import AsyncGenerator

import strawberry
from strawberry.types import Info

from app.core.config import settings
from app.events.base import Event
from app.events.redis_streams import RedisStreamsEventBus


@strawberry.type
class UserSubscription:
    @strawberry.subscription(description="Receive a welcome message when a user logs in.")
    async def user_logged_in(self, _info: Info, user_id: int) -> AsyncGenerator[str, None]:
        bus = RedisStreamsEventBus(redis_url=settings.REDIS_URL)
        await bus.connect()

        async def handler(event: Event):
            yield f"User {user_id} logged in. Event: {event.event_type}"

        await bus.subscribe("user.logged_in", handler)
        while True:
            await asyncio.sleep(1)
