import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_crud_flow(
    async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    resp = await async_client.get("/api/v1/users/", headers=auth_headers)
    assert resp.status_code == 403
