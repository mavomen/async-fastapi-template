"""Integration tests for user registration flow."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_full_registration_flow(async_client: AsyncClient, db_session: AsyncSession):
    """End-to-end: register a user, verify response structure."""
    payload = {
        "email": "flow@example.com",
        "username": "flowuser",
        "password": "FlowPass1!",
        "full_name": "Flow User",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "flow@example.com"
    assert data["username"] == "flowuser"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_registration_duplicate_email(async_client: AsyncClient, db_session: AsyncSession):
    """Attempting to register with an existing email should fail."""
    payload = {
        "email": "duplicate@example.com",
        "username": "first",
        "password": "FirstPass1!",
    }
    await async_client.post("/api/v1/auth/register", json=payload)

    dup = {
        "email": "duplicate@example.com",
        "username": "second",
        "password": "SecondPass1!",
    }
    response = await async_client.post("/api/v1/auth/register", json=dup)
    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower()
