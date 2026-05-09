"""Test profile avatar upload (no real file needed)."""

from io import BytesIO

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
        obj_in=UserCreate(
            email="avatar@test.com", username="avatar_test", password="Password1!"
        ),
    )
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_avatar_upload(async_client: AsyncClient, auth_headers: dict):
    """Uploading a placeholder avatar returns an img tag."""
    files = {"avatar": ("test.png", BytesIO(b"fakeimg"), "image/png")}
    resp = await async_client.post(
        "/profile/avatar",
        files=files,
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "img src" in resp.text
