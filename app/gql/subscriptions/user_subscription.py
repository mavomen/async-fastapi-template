"""User-related GraphQL subscription for real-time events."""

from typing import AsyncGenerator

import strawberry
from strawberry.types import Info

from app.core.config import settings
from app.events.base import Event


@strawberry.type
class UserSubscription:
    @strawberry.subscription(
        description="Receive a welcome message when a user logs in."
    )
    async def user_logged_in(
        self, info: Info, user_id: int
    ) -> AsyncGenerator[str, None]:
        # Subscribe to the event bus
        async with EventBus() as bus:
            await bus.connect()

            async def handler(event: Event):
                yield f"User {user_id} logged in. Event: {event.event_type}"

            await bus.subscribe("user.logged_in", handler)
            # Keep the connection alive until client disconnects
            while True:
                import asyncio

                await asyncio.sleep(1)
