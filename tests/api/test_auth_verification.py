"""Tests for email verification endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.identity.crud.user import user as crud_user
from app.identity.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_verify_request_endpoint_ok(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    """The verify-request endpoint returns 200 and the user remains unverified."""
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="verify@example.com",
            username="verifyuser",
            password="StrongPass1!",
        ),
    )
    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.post("/api/v1/auth/verify-request", headers=headers)
    assert response.status_code == 200

    # User should still be unverified (verification happens via email link)
    await db_session.refresh(user)
    assert user.is_verified is False


@pytest.mark.asyncio
async def test_verify_email_token_valid():
    """Generated verification token can be decoded."""
    from app.core.security import create_verification_token, decode_verification_token

    token = create_verification_token(42)
    payload = decode_verification_token(token)
    assert payload["sub"] == "42"
    assert payload["purpose"] == "email_verify"
