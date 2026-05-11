"""Test WebAuthn login-complete 401 branch."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_webauthn_login_complete_invalid(async_client: AsyncClient, db_session: AsyncSession):
    """Providing a bogus credential returns 401."""
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(email="w401@test.com", username="w401", password="Password1!"),
    )
    # Make complete_authentication return False so the endpoint raises 401
    with patch("app.api.endpoints.auth.complete_authentication", AsyncMock(return_value=False)):
        resp = await async_client.post(
            "/api/v1/auth/webauthn/login/complete",
            json={"user_id": "w401@test.com", "credential": {"rawId": "bogus"}},
        )
    assert resp.status_code == 401
