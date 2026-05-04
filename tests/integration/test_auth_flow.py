import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_login_and_access_protected_route(
    async_client: AsyncClient, test_user: dict, db_session: AsyncSession
):
    login_data = {"username": test_user["email"], "password": "Integration1!"}
    resp = await async_client.post("/api/v1/auth/login", data=login_data)
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_resp = await async_client.get("/api/v1/users/", headers=headers)
    assert user_resp.status_code in (200, 403)
