"""Test the JWKS endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_jwks(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/auth/.well-known/jwks.json")
    assert resp.status_code == 200
    assert "keys" in resp.json()
