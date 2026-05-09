"""Tests for email verification endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_verification_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_verify_request_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(email="check@test.com", username="check", password="Password1!"),
    )
    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await async_client.post("/api/v1/auth/verify-request", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_verify_email_invalid_token(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/auth/verify-email?token=bad.token")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_valid_token(async_client: AsyncClient, db_session: AsyncSession):
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(email="vvv@test.com", username="vvv", password="Password1!"),
    )
    token = create_verification_token(user.id)
    resp = await async_client.get(f"/api/v1/auth/verify-email?token={token}")
    assert resp.status_code == 200
    await db_session.refresh(user)
    assert user.is_verified is True
