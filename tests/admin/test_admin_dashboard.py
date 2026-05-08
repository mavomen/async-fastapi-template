"""Tests for HTMX admin dashboard."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.models.role import Permission, Role
from app.schemas.user import UserCreate


@pytest.fixture
async def admin_headers(db_session: AsyncSession) -> dict:
    """Create a superuser / admin user with necessary permissions and return auth headers."""
    # Create required permissions
    perms = {}
    for perm_name in ["user:admin", "role:admin", "permission:admin"]:
        perm = Permission(name=perm_name)
        db_session.add(perm)
        perms[perm_name] = perm
    await db_session.flush()

    # Create admin role and assign permissions
    role = Role(name="admin")
    role.permissions.extend(perms.values())
    db_session.add(role)
    await db_session.flush()

    # Create admin user
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="admin@example.com", username="admin", password="AdminPass1!"
        ),
    )
    user.roles.append(role)
    await db_session.commit()

    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_dashboard_accessible(
    async_client: AsyncClient, admin_headers: dict
):
    """Admin dashboard home page loads."""
    response = await async_client.get("/admin", headers=admin_headers)
    assert response.status_code == 200
    assert "Admin Dashboard" in response.text


@pytest.mark.asyncio
async def test_admin_user_list(async_client: AsyncClient, admin_headers: dict):
    """User list page renders with admin permission."""
    response = await async_client.get("/admin/users", headers=admin_headers)
    assert response.status_code == 200
    assert "admin" in response.text


@pytest.mark.asyncio
async def test_admin_user_detail(async_client: AsyncClient, admin_headers: dict):
    """View a single user detail page."""
    import re

    list_resp = await async_client.get("/admin/users", headers=admin_headers)
    match = re.search(r"/admin/users/(\d+)/edit", list_resp.text)
    assert match, "No user row found in admin list"
    user_id = match.group(1)

    detail_resp = await async_client.get(
        f"/admin/users/{user_id}", headers=admin_headers
    )
    assert detail_resp.status_code == 200
    assert "admin" in detail_resp.text


@pytest.mark.asyncio
async def test_admin_user_edit_form_loads(
    async_client: AsyncClient, admin_headers: dict
):
    """Edit form page loads for a user."""
    import re

    list_resp = await async_client.get("/admin/users", headers=admin_headers)
    match = re.search(r"/admin/users/(\d+)/edit", list_resp.text)
    assert match, "No user row found"
    user_id = match.group(1)

    edit_resp = await async_client.get(
        f"/admin/users/{user_id}/edit", headers=admin_headers
    )
    assert edit_resp.status_code == 200
    assert "Edit" in edit_resp.text


@pytest.mark.asyncio
async def test_admin_forbidden_for_regular_user(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Regular user without admin role should get 403."""
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="pleb@example.com", username="pleb", password="Password1!"
        ),
    )
    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}
    response = await async_client.get("/admin", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_role_delete(
    async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    """Delete a role via the admin panel."""
    from app.models.role import Role

    role = Role(name="temp_role_to_delete", description="Temp role")
    db_session.add(role)
    await db_session.commit()

    delete_resp = await async_client.get(
        f"/admin/roles/{role.id}/delete",
        headers=admin_headers,
        follow_redirects=True,
    )
    assert delete_resp.status_code == 200
    assert "temp_role_to_delete" not in delete_resp.text


@pytest.mark.asyncio
async def test_admin_permission_delete(
    async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    """Delete a permission via the admin panel."""
    from app.models.role import Permission

    perm = Permission(name="temp_perm_to_delete", description="Temp perm")
    db_session.add(perm)
    await db_session.commit()

    delete_resp = await async_client.get(
        f"/admin/permissions/{perm.id}/delete",
        headers=admin_headers,
        follow_redirects=True,
    )
    assert delete_resp.status_code == 200
    assert "temp_perm_to_delete" not in delete_resp.text


@pytest.mark.asyncio
async def test_admin_user_search(async_client: AsyncClient, admin_headers: dict):
    """Search for a user via the admin list page."""
    response = await async_client.get(
        "/admin/users?search=admin",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert "admin" in response.text

@pytest.mark.asyncio
async def test_admin_role_detail(async_client: AsyncClient, admin_headers: dict):
    """View a role detail page via admin."""
    import re
    roles_resp = await async_client.get("/admin/roles", headers=admin_headers)
    match = re.search(r'/admin/roles/(\d+)/edit', roles_resp.text)
    assert match, "No role row found"
    role_id = match.group(1)

    detail_resp = await async_client.get(f"/admin/roles/{role_id}", headers=admin_headers)
    assert detail_resp.status_code == 200
    assert "admin" in detail_resp.text  # role name should appear

@pytest.mark.asyncio
async def test_admin_user_list_pagination(async_client: AsyncClient, admin_headers: dict):
    """User list page with page parameter works."""
    response = await async_client.get("/admin/users?page=1", headers=admin_headers)
    assert response.status_code == 200
