"""Unit test for GraphQL subscription generator."""

import pytest

from app.gql.subscriptions.user_subscription import UserSubscription


@pytest.mark.asyncio
async def test_user_logged_in_subscription():
    sub = UserSubscription()
    count = 0
    async for _msg in sub.user_logged_in(_info=None, user_id=1):
        count += 1
        if count >= 5:
            break
    assert count == 5
