"""Test profile edit endpoint (mocked DB)."""

from unittest.mock import AsyncMock, patch

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
        obj_in=UserCreate(email="prof@test.com", username="prof", password="Password1!"),
    )
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_profile_edit_full_name(async_client: AsyncClient, auth_headers: dict):
    """Sending full_name updates the user."""
    with patch("app.auth.profile.crud_user.update", new_callable=AsyncMock) as mock_update:
        resp = await async_client.post(
            "/profile/edit",
            data={"full_name": "New Name"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_profile_edit_email(async_client: AsyncClient, auth_headers: dict):
    """Sending email updates the user."""
    with patch("app.auth.profile.crud_user.update", new_callable=AsyncMock) as mock_update:
        resp = await async_client.post(
            "/profile/edit",
            data={"email": "new@example.com"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    mock_update.assert_called_once()
