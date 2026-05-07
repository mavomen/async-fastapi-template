"""Tests for CSV user import endpoint."""

import io

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.models.role import Permission, Role
from app.schemas.user import UserCreate


@pytest.fixture
async def admin_headers(db_session: AsyncSession) -> dict:
    """Create admin user with user:write permission and return auth headers."""
    # Create permission
    perm = Permission(name="user:write")
    db_session.add(perm)
    role = Role(name="admin")
    role.permissions.append(perm)
    db_session.add(role)
    await db_session.flush()

    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="csvadmin@example.com", username="csvadmin", password="AdminPass1!"
        ),
    )
    user.roles.append(role)
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_csv_import(
    async_client: AsyncClient,
    admin_headers: dict,
    db_session: AsyncSession,
):
    """Import users from a CSV file."""
    csv_content = (
        "email,username,password,full_name\n"
        "csv1@example.com,csvuser1,Pass1234!,CSV One\n"
        "csv2@example.com,csvuser2,Pass5678!,CSV Two\n"
    )
    files = {"file": ("users.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    response = await async_client.post(
        "/api/v1/users/import/csv", files=files, headers=admin_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 2
    emails = [u["email"] for u in data]
    assert "csv1@example.com" in emails
    assert "csv2@example.com" in emails
