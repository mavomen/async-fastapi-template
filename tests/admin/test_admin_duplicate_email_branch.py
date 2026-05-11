"""Test admin duplicate email edge cases."""

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
            email="superadmin_dup@test.com",
            username="superadmin_dup",
            password="AdminPass1!",
        ),
    )
    user.is_superuser = True
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_create_duplicate_email(
    async_client: AsyncClient, super_headers: dict, db_session: AsyncSession
):
    """Creating a user with an existing email returns 400."""
    await crud_user.create(
        db_session,
        obj_in=UserCreate(email="dupcheck@test.com", username="dupcheck1", password="Password1!"),
    )
    await db_session.commit()

    resp = await async_client.post(
        "/admin/users/create",
        data={
            "email": "dupcheck@test.com",
            "username": "dupcheck2",
            "password": "Password1!",
            "full_name": "Dup",
            "is_active": "1",
            "is_verified": "0",
        },
        headers=super_headers,
    )
    assert resp.status_code == 400
    assert "Email already exists" in resp.json()["detail"]
