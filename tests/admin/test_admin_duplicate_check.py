"""Admin duplicate email check tests."""

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
            email="dupadmin@test.com", username="dupadmin", password="AdminPass1!"
        ),
    )
    user.is_superuser = True
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_create_duplicate_user(
    async_client: AsyncClient, super_headers: dict, db_session: AsyncSession
):
    """Creating a user with an existing email returns 400."""
    # Create the first user directly in the DB
    await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="dupuser@test.com", username="dupuser1", password="Password1!"
        ),
    )
    await db_session.commit()

    # Try to create another with the same email via admin
    resp = await async_client.post(
        "/admin/users/create",
        data={
            "email": "dupuser@test.com",
            "username": "dupuser2",
            "full_name": "Duplicate",
            "is_active": "1",
            "is_verified": "0",
        },
        headers=super_headers,
    )
    assert resp.status_code == 400
    assert "Email already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_edit_to_duplicate_email(
    async_client: AsyncClient, super_headers: dict, db_session: AsyncSession
):
    """Editing a user to an existing email returns 400."""
    user1 = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="editdup1@test.com", username="editdup1", password="Password1!"
        ),
    )
    user2 = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="editdup2@test.com", username="editdup2", password="Password1!"
        ),
    )
    await db_session.commit()

    resp = await async_client.post(
        f"/admin/users/{user2.id}/edit",
        data={
            "email": "editdup1@test.com",  # already taken by user1
            "username": "editdup2",
            "full_name": "Edited",
            "is_active": "1",
            "is_verified": "1",
        },
        headers=super_headers,
    )
    assert resp.status_code == 400
    assert "Email already exists" in resp.json()["detail"]
