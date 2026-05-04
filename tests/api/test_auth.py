"""
Tests for authentication endpoints (register, login).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient, db_session: AsyncSession):
    """Register a new user successfully."""
    user_data = {
        "email": "newuser@example.com",
        "username": "newuser",
        "password": "StrongPass123!",
        "full_name": "New User",
    }
    response = await async_client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["username"] == "newuser"
    assert data["is_active"] is True
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient, db_session: AsyncSession):
    """Register with an existing email should fail."""
    user_data = {
        "email": "duplicate@example.com",
        "username": "user1",
        "password": "StrongPass123!",
    }
    # Create first user
    await crud_user.create(db_session, obj_in=UserCreate(**user_data))
    duplicate = {
        "email": "duplicate@example.com",
        "username": "user2",
        "password": "StrongPass123!",
    }
    response = await async_client.post("/api/v1/auth/register", json=duplicate)
    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_duplicate_username(async_client: AsyncClient, db_session: AsyncSession):
    """Register with an existing username should fail."""
    user_data = {
        "email": "user1@example.com",
        "username": "uniqueusername",
        "password": "StrongPass123!",
    }
    await crud_user.create(db_session, obj_in=UserCreate(**user_data))
    duplicate = {
        "email": "user2@example.com",
        "username": "uniqueusername",
        "password": "StrongPass123!",
    }
    response = await async_client.post("/api/v1/auth/register", json=duplicate)
    assert response.status_code == 400
    assert "username" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_missing_fields(async_client: AsyncClient, db_session: AsyncSession):
    """Register with missing required fields returns validation error."""
    response = await async_client.post("/api/v1/auth/register", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_weak_password(async_client: AsyncClient, db_session: AsyncSession):
    """Password too short should fail validation."""
    user_data = {
        "email": "weak@example.com",
        "username": "weakuser",
        "password": "short",
    }
    response = await async_client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, db_session: AsyncSession):
    """Log in with correct credentials returns access token."""
    user_data = UserCreate(
        email="login@example.com",
        username="loginuser",
        password="CorrectPass1!",
    )
    await crud_user.create(db_session, obj_in=user_data)

    form_data = {
        "username": "login@example.com",
        "password": "CorrectPass1!",
    }
    response = await async_client.post("/api/v1/auth/login", data=form_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    token = data["access_token"]
    assert len(token.split(".")) == 3


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, db_session: AsyncSession):
    """Login with wrong password returns 401."""
    user_data = UserCreate(
        email="wrongpw@example.com",
        username="wrongpwuser",
        password="RightPassword1!",
    )
    await crud_user.create(db_session, obj_in=user_data)

    form_data = {
        "username": "wrongpw@example.com",
        "password": "WrongPassword1!",
    }
    response = await async_client.post("/api/v1/auth/login", data=form_data)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient, db_session: AsyncSession):
    """Login with an email that doesn't exist returns 401."""
    form_data = {
        "username": "nobody@example.com",
        "password": "SomePassword1!",
    }
    response = await async_client.post("/api/v1/auth/login", data=form_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(async_client: AsyncClient, db_session: AsyncSession):
    """Login with an inactive user should still return a token (current behaviour)."""
    user_data = UserCreate(
        email="inactive@example.com",
        username="inactiveuser",
        password="ValidPass1!",
    )
    user = await crud_user.create(db_session, obj_in=user_data)
    user.is_active = False
    db_session.add(user)
    await db_session.commit()

    form_data = {
        "username": "inactive@example.com",
        "password": "ValidPass1!",
    }
    response = await async_client.post("/api/v1/auth/login", data=form_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
