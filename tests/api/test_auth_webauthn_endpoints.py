"""Tests for WebAuthn HTTP endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.fixture
async def auth_headers(db_session: AsyncSession) -> dict:
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(email="webauthn@test.com", username="webauthn", password="Password1!"),
    )
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_webauthn_register_begin(async_client: AsyncClient, auth_headers: dict):
    """Register begin returns public key options."""
    with patch("app.api.endpoints.auth.begin_registration") as mock_begin:
        mock_begin.return_value = {"rp": {"name": "Test"}, "challenge": "abc"}
        resp = await async_client.post("/api/v1/auth/webauthn/register/begin", headers=auth_headers)
    assert resp.status_code == 200
    assert "rp" in resp.json()


@pytest.mark.asyncio
async def test_webauthn_login_begin(async_client: AsyncClient):
    """Login begin returns authentication options (mocked DB)."""
    fake_user = MagicMock()
    fake_user.id = 99
    fake_user.email = "fake@test.com"

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    with (
        patch("app.api.endpoints.auth.begin_authentication") as mock_begin_opt,
        patch("app.core.database.sessionmanager.session") as mock_sess,
        patch("app.api.endpoints.auth.crud_user.get_by_email") as mock_get_user,
    ):
        mock_sess.return_value = mock_session
        mock_get_user.return_value = fake_user
        mock_begin_opt.return_value = {"challenge": "abc", "allowCredentials": []}

        resp = await async_client.post(
            "/api/v1/auth/webauthn/login/begin",
            json={"user_id": "any@email.com"},
        )
    assert resp.status_code == 200
    assert "challenge" in resp.json()
