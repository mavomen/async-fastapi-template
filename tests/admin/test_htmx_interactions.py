"""Tests for HTMX admin interactions."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.identity.crud.user import user as crud_user
from app.identity.schemas.user import UserCreate


@pytest.fixture
async def su_headers(db_session: AsyncSession) -> dict:
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(email="htmxadmin@test.com", username="htmxadmin", password="AdminPass1!"),
    )
    user.is_superuser = True
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_search_returns_partial(async_client: AsyncClient, su_headers: dict):
    """Search returns a partial HTML table."""
    resp = await async_client.get(
        "/admin/users?search=htmxadmin",
        headers={**su_headers, "HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "htmxadmin" in resp.text


@pytest.mark.asyncio
async def test_profile_page_loads(async_client: AsyncClient, su_headers: dict):
    """Profile page renders."""
    resp = await async_client.get("/profile", headers=su_headers)
    assert resp.status_code == 200
    assert "Profile" in resp.text


@pytest.mark.asyncio
async def test_graphql_playground_loads(async_client: AsyncClient):
    """GraphQL playground page renders."""
    resp = await async_client.get("/gql/playground")
    assert resp.status_code == 200
    assert "GraphQL Playground" in resp.text
