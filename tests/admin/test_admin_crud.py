"""Admin CRUD workflow tests (uses superuser to avoid RBAC edge cases)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate


@pytest.fixture
async def superuser_headers(db_session: AsyncSession) -> dict:
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="superadmin@example.com",
            username="superadmin",
            password="SuperPass1!",
        ),
    )
    user.is_superuser = True
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_create_and_edit_role(async_client: AsyncClient, superuser_headers: dict):
    """Create a new role via admin, then edit it."""
    # Create
    resp = await async_client.post(
        "/admin/roles/create",
        data={"name": "test-role", "description": "tmp"},
        headers=superuser_headers,
        follow_redirects=True,
    )
    assert resp.status_code == 200, f"Create role failed: {resp.text}"
    assert "test-role" in resp.text

    # Find its ID from the list
    import re

    list_resp = await async_client.get("/admin/roles", headers=superuser_headers)
    match = re.search(r"/admin/roles/(\d+)/edit", list_resp.text)
    assert match, "No role row found"
    role_id = match.group(1)

    # Edit
    edit_resp = await async_client.post(
        f"/admin/roles/{role_id}/edit",
        data={"name": "test-role-edited", "description": "updated"},
        headers=superuser_headers,
        follow_redirects=True,
    )
    assert edit_resp.status_code == 200, f"Edit role failed: {edit_resp.text}"
    assert "test-role-edited" in edit_resp.text


@pytest.mark.asyncio
async def test_admin_create_and_delete_permission(
    async_client: AsyncClient, superuser_headers: dict
):
    """Create a permission then delete it via admin."""
    resp = await async_client.post(
        "/admin/permissions/create",
        data={"name": "temp-perm", "description": "tmp"},
        headers=superuser_headers,
        follow_redirects=True,
    )
    assert resp.status_code == 200, f"Create permission failed: {resp.text}"

    import re

    list_resp = await async_client.get("/admin/permissions", headers=superuser_headers)
    match = re.search(r"/admin/permissions/(\d+)/edit", list_resp.text)
    assert match, "No permission row found"
    perm_id = match.group(1)

    del_resp = await async_client.post(
        f"/admin/permissions/{perm_id}/delete",
        headers=superuser_headers,
        follow_redirects=True,
    )
    assert del_resp.status_code == 200
    assert "temp-perm" not in del_resp.text
