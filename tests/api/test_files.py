"""Tests for file endpoints."""

from io import BytesIO

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.identity.crud.user import user as crud_user
from app.identity.schemas.user import UserCreate


@pytest.fixture
async def auth_headers(db_session: AsyncSession):
    """Create a user and return auth headers."""
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="fileuser@example.com",
            username="fileuser",
            password="StrongPass1!",
        ),
    )
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_upload_file(async_client: AsyncClient, auth_headers: dict):
    file_content = b"dummy content"
    files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
    response = await async_client.post(
        "/api/v1/files/upload",
        files=files,
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["path"] == "test.txt"

    # Download the file
    response = await async_client.get(
        f"/api/v1/files/download/{data['path']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.content == file_content


@pytest.mark.asyncio
async def test_upload_without_auth(async_client: AsyncClient):
    response = await async_client.post("/api/v1/files/upload")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_download_nonexistent(async_client: AsyncClient, auth_headers: dict):
    response = await async_client.get(
        "/api/v1/files/download/nonexistent.txt",
        headers=auth_headers,
    )
    assert response.status_code == 404
