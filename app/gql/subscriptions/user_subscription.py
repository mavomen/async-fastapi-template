"""User-related GraphQL subscription for real-time events."""

import asyncio
from collections.abc import AsyncGenerator

import strawberry
from strawberry.types import Info

"""User-related GraphQL subscription for real-time events."""


@strawberry.type
class UserSubscription:
    @strawberry.subscription(
        description="Receive a countdown when a user logs in. Demo only."
    )
    async def user_logged_in(
        self, _info: Info, user_id: int
    ) -> AsyncGenerator[str, None]:
        for i in range(5, 0, -1):
            yield f"User {user_id} logged in. Countdown: {i}"
            await asyncio.sleep(1)
        yield f"User {user_id} is ready!"
