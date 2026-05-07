"""Tests for GraphQL user queries."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_me_query(async_client: AsyncClient, db_session: AsyncSession):
    """Test the 'me' query returns the current user."""
    # Create a user and get a token
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="gqlme@example.com", username="gqlme", password="StrongPass1!"
        ),
    )
    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    query = "{ me { id email username } }"
    response = await async_client.post(
        "/graphql", json={"query": query}, headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "errors" not in data
    assert data["data"]["me"]["email"] == "gqlme@example.com"


@pytest.mark.asyncio
async def test_user_query_requires_permission(async_client: AsyncClient):
    """Test that 'user' query needs authentication."""
    query = "{ user(userId: 1) { id } }"
    response = await async_client.post("/graphql", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    # Should be an error because no current_user
    assert "errors" in data
