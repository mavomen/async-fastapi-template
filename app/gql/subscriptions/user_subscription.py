"""User-related GraphQL subscription for real-time events."""

"""User-related GraphQL subscription for real-time events."""

import asyncio
from typing import AsyncGenerator

import strawberry
from strawberry.types import Info


@strawberry.type
class UserSubscription:
    """Subscriptions for real-time user events."""

    @strawberry.subscription(
        description="Receive a countdown when a user logs in. Demo only."
    )
    async def user_logged_in(
        self, info: Info, user_id: int
    ) -> AsyncGenerator[str, None]:
        """Demo subscription that emits a countdown after a user logs in."""
        for i in range(5, 0, -1):
            yield f"User {user_id} logged in. Countdown: {i}"
            await asyncio.sleep(1)
        yield f"User {user_id} is ready!"
