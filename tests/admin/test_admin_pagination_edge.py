"""Test admin pagination with higher page number."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.fixture
async def super_headers(db_session: AsyncSession) -> dict:
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(email="pag@admin.com", username="pagadmin", password="AdminPass1!"),
    )
    user.is_superuser = True
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_users_page_two(async_client: AsyncClient, super_headers: dict):
    """Requesting page 2 of users (even when empty) returns 200."""
    resp = await async_client.get("/admin/users?page=2", headers=super_headers)
    assert resp.status_code == 200
