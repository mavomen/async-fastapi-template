"""Fixtures specific to integration tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> dict:
    """Create a user and return its data plus auth token."""
    user_in = UserCreate(
        email="integration@example.com",
        username="integration",
        password="Integration1!",
        full_name="Integration Test",
    )
    user = await crud_user.create(db_session, obj_in=user_in)
    token = create_access_token(subject=user.id)
    return {
        "id": user.id,
        "email": user.email,
        "token": token,
    }


@pytest.fixture(scope="function")
def auth_headers(test_user: dict) -> dict:
    """Return Authorization headers for the test user."""
    return {"Authorization": f"Bearer {test_user['token']}"}
