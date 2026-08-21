"""Tests for CSV user import endpoint."""

import io

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.models.role import Permission, Role
from app.models.user import User
from app.schemas.user import UserCreate


@pytest.fixture
async def admin_headers(db_session: AsyncSession) -> dict:
    """Create admin user with user:write permission and return auth headers."""
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


def _csv_bytes(rows: list[str]) -> bytes:
    header = "email,username,password,full_name"
    return "\n".join([header, *rows]).encode()


@pytest.mark.asyncio
async def test_csv_import(async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession):
    """Import two users from a CSV file in a single commit."""
    csv_content = _csv_bytes(
        [
            "csv1@example.com,csvuser1,Pass1234!,CSV One",
            "csv2@example.com,csvuser2,Pass5678!,CSV Two",
        ]
    )
    resp = await async_client.post(
        "/api/v1/users/import/csv",
        files={"file": ("users.csv", io.BytesIO(csv_content), "text/csv")},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 2
    emails = {u["email"] for u in data}
    assert emails == {"csv1@example.com", "csv2@example.com"}


@pytest.mark.asyncio
async def test_csv_import_skips_duplicates(
    async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    """Duplicate emails in the CSV are skipped (pre-filtered)."""
    csv_content = _csv_bytes(
        [
            "dup@example.com,dupuser,Pass1234!,Dup User",
            "dup@example.com,dupuser2,Pass5678!,Dup User 2",
        ]
    )
    resp = await async_client.post(
        "/api/v1/users/import/csv",
        files={"file": ("users.csv", io.BytesIO(csv_content), "text/csv")},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 1

    # Also skip emails that already exist in the database
    csv_content2 = _csv_bytes(
        [
            "dup@example.com,existing,Pass9999!,Existing",
        ]
    )
    resp2 = await async_client.post(
        "/api/v1/users/import/csv",
        files={"file": ("users.csv", io.BytesIO(csv_content2), "text/csv")},
        headers=admin_headers,
    )
    assert resp2.status_code == 201
    assert len(resp2.json()) == 0


@pytest.mark.asyncio
async def test_csv_import_empty_file(async_client: AsyncClient, admin_headers: dict):
    """An empty CSV returns an empty list."""
    csv_content = b"email,username,password,full_name\n"
    resp = await async_client.post(
        "/api/v1/users/import/csv",
        files={"file": ("users.csv", io.BytesIO(csv_content), "text/csv")},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json() == []


@pytest.mark.asyncio
async def test_csv_import_passwords_are_hashed(
    async_client: AsyncClient, admin_headers: dict, db_session: AsyncSession
):
    """Imported passwords must be bcrypt hashes, not plaintext."""
    csv_content = _csv_bytes(
        [
            "hash@example.com,hashuser,MyPassword1!,Hashed",
        ]
    )
    await async_client.post(
        "/api/v1/users/import/csv",
        files={"file": ("users.csv", io.BytesIO(csv_content), "text/csv")},
        headers=admin_headers,
    )
    result = await db_session.execute(select(User).where(User.email == "hash@example.com"))
    user = result.scalar_one()
    assert user.hashed_password.startswith("$2")
    assert user.hashed_password != "MyPassword1!"
