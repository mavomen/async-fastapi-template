"""Tests for refresh token flow."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.crud.user import user as crud_user
from app.identity.schemas.user import UserCreate


@pytest.fixture
async def test_user(db_session: AsyncSession) -> dict:
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(email="refresh@test.com", username="refresh", password="Password1!"),
    )
    return {"id": user.id, "email": user.email}


@pytest.mark.asyncio
async def test_login_returns_refresh_token(async_client: AsyncClient, test_user: dict):
    resp = await async_client.post(
        "/api/v1/auth/login",
        data={"username": "refresh@test.com", "password": "Password1!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_token_returns_new_tokens(async_client: AsyncClient, test_user: dict):
    # First login to get a refresh token
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        data={"username": "refresh@test.com", "password": "Password1!"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await async_client.post(
        "/api/v1/auth/refresh",
        data={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data  # rotation


@pytest.mark.asyncio
async def test_refresh_with_invalid_token(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/v1/auth/refresh",
        data={"refresh_token": "invalid.token.here"},
    )
    assert resp.status_code == 401
