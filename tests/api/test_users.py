"""Tests for user management endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.identity.crud.user import user as crud_user
from app.identity.models.role import Permission, Role
from app.identity.schemas.user import UserCreate


async def seed_role_and_permission(db_session: AsyncSession):
    """Create a role with user:read/write/delete permissions and assign to a user."""
    # Create permissions
    perms = {}
    for name in ["user:read", "user:write", "user:delete"]:
        perm = Permission(name=name)
        db_session.add(perm)
        perms[name] = perm
    await db_session.flush()

    # Create role
    role = Role(name="admin")
    role.permissions.extend(perms.values())
    db_session.add(role)
    await db_session.flush()

    return role, perms


@pytest.fixture
async def admin_headers(db_session: AsyncSession, async_client: AsyncClient):
    """Create a user with admin role and return auth headers."""
    role, _ = await seed_role_and_permission(db_session)

    # Create user
    user_create = UserCreate(
        email="admin@example.com",
        username="admin",
        password="AdminPass123!",
        full_name="Admin",
    )
    user = await crud_user.create(db_session, obj_in=user_create)
    # Assign admin role
    user.roles.append(role)
    await db_session.commit()

    # Generate token
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def normal_user_headers(db_session: AsyncSession, async_client: AsyncClient):
    """Create a normal user without special permissions."""
    user_create = UserCreate(
        email="normal@example.com",
        username="normal",
        password="NormalPass123!",
    )
    user = await crud_user.create(db_session, obj_in=user_create)
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_users_requires_permission(async_client: AsyncClient, normal_user_headers: dict):
    response = await async_client.get("/api/v1/users/", headers=normal_user_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_as_admin(async_client: AsyncClient, admin_headers: dict):
    response = await async_client.get("/api/v1/users/", headers=admin_headers)
    assert response.status_code == 200
    # Should contain at least the admin user
    data = response.json()
    assert any(u["email"] == "admin@example.com" for u in data)


@pytest.mark.asyncio
async def test_get_user_not_found(async_client: AsyncClient, admin_headers: dict):
    response = await async_client.get("/api/v1/users/99999", headers=admin_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_user_as_admin(
    async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    # Create a user to update
    user_create = UserCreate(email="target@example.com", username="target", password="Pass123!")
    user = await crud_user.create(db_session, obj_in=user_create)

    update_data = {"full_name": "Updated Name"}
    response = await async_client.patch(
        f"/api/v1/users/{user.id}", json=update_data, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_user_requires_permission(
    async_client: AsyncClient, normal_user_headers: dict, db_session: AsyncSession
):
    user_create = UserCreate(email="victim@example.com", username="victim", password="Pass123!")
    user = await crud_user.create(db_session, obj_in=user_create)

    update_data = {"full_name": "Hacked"}
    response = await async_client.patch(
        f"/api/v1/users/{user.id}", json=update_data, headers=normal_user_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_as_admin(
    async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    user_create = UserCreate(email="delete@example.com", username="deleteuser", password="Pass123!")
    user = await crud_user.create(db_session, obj_in=user_create)

    response = await async_client.delete(f"/api/v1/users/{user.id}", headers=admin_headers)
    assert response.status_code == 200

    # Verify deletion
    deleted = await crud_user.get(db_session, id=user.id)
    assert deleted is None


@pytest.mark.asyncio
async def test_delete_user_requires_permission(
    async_client: AsyncClient, normal_user_headers: dict, db_session: AsyncSession
):
    user_create = UserCreate(
        email="dontdelete@example.com", username="dontdelete", password="Pass123!"
    )
    user = await crud_user.create(db_session, obj_in=user_create)

    response = await async_client.delete(f"/api/v1/users/{user.id}", headers=normal_user_headers)
    assert response.status_code == 403
