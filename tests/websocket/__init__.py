"""Tests for WebSocket chat endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.identity.crud.user import user as crud_user
from app.identity.schemas.user import UserCreate


@pytest.fixture
async def ws_token(db_session: AsyncSession) -> str:
    """Create a user and return a valid access token."""
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="wstester@example.com",
            username="wstester",
            password="StrongPass1!",
        ),
    )
    return create_access_token(subject=user.id)


@pytest.mark.asyncio
async def test_websocket_connect_and_chat(async_client: AsyncClient, ws_token: str):
    """Connect with a valid token, send a message, and receive the broadcast."""
    url = f"/ws/chat?token={ws_token}"
    async with async_client.websocket_connect(url) as websocket:
        await websocket.send_text("Hello world")
        response = await websocket.receive_text()
        assert "Hello world" in response


@pytest.mark.asyncio
async def test_websocket_invalid_token(async_client: AsyncClient):
    """Connecting with an invalid token should fail."""
    url = "/ws/chat?token=invalid.token.here"
    with pytest.raises(Exception):
        async with async_client.websocket_connect(url):
            pass


@pytest.mark.asyncio
async def test_websocket_missing_token(async_client: AsyncClient):
    """Connecting without a token should fail."""
    url = "/ws/chat"
    with pytest.raises(Exception):
        async with async_client.websocket_connect(url):
            pass
