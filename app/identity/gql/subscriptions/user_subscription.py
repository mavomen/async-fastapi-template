"""User-related GraphQL subscription for real-time events."""

import asyncio
from collections.abc import AsyncGenerator

import strawberry
from strawberry.types import Info

from app.events import get_event_bus
from app.events.base import Event


@strawberry.type
class UserSubscription:
    @strawberry.subscription(description="Receive a welcome message when a user logs in.")  # type: ignore[untyped-decorator]
    async def user_logged_in(self, _info: Info, _user_id: int) -> AsyncGenerator[str, None]:
        bus = await get_event_bus()

        async def handler(event: Event) -> None:
            event_bus = await get_event_bus()
            await event_bus.publish(event)

        await bus.subscribe("user.logged_in", handler)
        try:
            while True:
                await asyncio.sleep(1)
        finally:
            await bus.unsubscribe("user.logged_in", handler)
