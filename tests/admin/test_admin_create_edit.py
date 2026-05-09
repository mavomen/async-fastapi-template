"""Admin CRUD create/edit test for coverage of form handling."""

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
        obj_in=UserCreate(
            email="admincoverage@test.com",
            username="admincoverage",
            password="AdminPass1!",
        ),
    )
    user.is_superuser = True
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_create_and_edit_permission(async_client: AsyncClient, super_headers: dict):
    """Create a permission then edit it — covers coerce/password helpers."""
    resp = await async_client.post(
        "/admin/permissions/create",
        data={"name": "tempperm", "description": "test"},
        headers=super_headers,
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "tempperm" in resp.text

    import re

    list_resp = await async_client.get("/admin/permissions", headers=super_headers)
    match = re.search(r"/admin/permissions/(\d+)/edit", list_resp.text)
    assert match
    perm_id = match.group(1)

    edit_resp = await async_client.post(
        f"/admin/permissions/{perm_id}/edit",
        data={"name": "tempperm-edited", "description": "updated"},
        headers=super_headers,
        follow_redirects=True,
    )
    assert edit_resp.status_code == 200
    assert "tempperm-edited" in edit_resp.text
