"""Test admin create role endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.fixture
async def super_headers(db_session: AsyncSession) -> dict:
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="superadminrole@test.com",
            username="superadminrole",
            password="AdminPass1!",
        ),
    )
    user.is_superuser = True
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_create_role(async_client: AsyncClient, super_headers: dict):
    """Create a role via admin panel."""
    resp = await async_client.post(
        "/admin/roles/create",
        data={"name": "test-role-admin", "description": "a test role"},
        headers=super_headers,
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "test-role-admin" in resp.text
