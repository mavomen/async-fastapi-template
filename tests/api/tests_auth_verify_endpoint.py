"""Integration test for email verification endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate
from app.core.security import create_verification_token


@pytest.mark.asyncio
async def test_verify_email_success(async_client: AsyncClient, db_session: AsyncSession):
    """Verify an email with a valid token."""
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(email="verify-test@example.com", username="verifytest", password="Password1!"),
    )
    token = create_verification_token(user.id)
    resp = await async_client.get(f"/api/v1/auth/verify-email?token={token}")
    assert resp.status_code == 200
    await db_session.refresh(user)
    assert user.is_verified is True
