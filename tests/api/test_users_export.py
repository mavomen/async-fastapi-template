"""Test user export endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.identity.crud.user import user as crud_user
from app.identity.models.role import Permission, Role
from app.identity.schemas.user import UserCreate


@pytest.fixture
async def admin_headers(db_session: AsyncSession) -> dict:
    perm = Permission(name="user:read")
    db_session.add(perm)
    role = Role(name="reader")
    role.permissions.append(perm)
    db_session.add(role)
    await db_session.flush()

    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="exportadmin@test.com", username="exportadmin", password="AdminPass1!"
        ),
    )
    user.roles.append(role)
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_export_csv(async_client: AsyncClient, admin_headers: dict):
    resp = await async_client.get("/api/v1/users/export?format=csv", headers=admin_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_excel(async_client: AsyncClient, admin_headers: dict):
    resp = await async_client.get("/api/v1/users/export?format=excel", headers=admin_headers)
    assert resp.status_code == 200
