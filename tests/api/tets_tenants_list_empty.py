"""Cover the empty tenants list endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.fixture
async def su_headers(db_session: AsyncSession) -> dict:
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="tenantsu@test.com", username="tenantsu", password="SuperPass1!"
        ),
    )
    user.is_superuser = True
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_tenants_empty(async_client: AsyncClient, su_headers: dict):
    resp = await async_client.get("/api/v1/tenants/", headers=su_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
