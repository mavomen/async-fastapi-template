"""Integration tests for multi-tenancy."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.fixture
async def superuser_token(db_session: AsyncSession) -> str:
    """Create a superuser and return JWT token."""
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(email="super@example.com", username="super", password="SuperPass1!"),
    )
    user.is_superuser = True
    await db_session.commit()
    return create_access_token(subject=user.id)


@pytest.mark.asyncio
async def test_create_tenant_requires_superuser(async_client: AsyncClient):
    """Only superuser can create a tenant."""
    headers = {"Authorization": "Bearer fake-token"}
    resp = await async_client.post("/api/v1/tenants/", headers=headers, json={"name": "TestCorp"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_tenant_as_superuser(async_client: AsyncClient, superuser_token: str):
    """Superuser can create a tenant."""
    headers = {"Authorization": f"Bearer {superuser_token}"}
    resp = await async_client.post(
        "/api/v1/tenants/",
        headers=headers,
        json={"name": "Acme Inc", "slug": "acme"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "Acme Inc"
    assert data["slug"] == "acme"
