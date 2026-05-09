"""Unit tests for WebSocket auth dependency (no HTTP)."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from app.websocket.auth import get_current_user_ws


@pytest.mark.asyncio
async def test_auth_no_token():
    ws = AsyncMock(spec=WebSocket)
    ws.query_params = {}
    with pytest.raises(WebSocketDisconnect):
        await get_current_user_ws(ws)


@pytest.mark.asyncio
async def test_auth_valid_token():
    ws = AsyncMock(spec=WebSocket)
    ws.query_params = {"token": "valid"}
    with (
        patch("app.websocket.auth.decode_access_token") as mock_decode,
        patch("app.websocket.auth.crud_user.get") as mock_get_user,
        patch("app.websocket.auth.sessionmanager.session") as mock_session,
    ):
        mock_decode.return_value = {"sub": "42"}
        mock_get_user.return_value = AsyncMock(id=42)
        mock_session.return_value.__aenter__.return_value = AsyncMock()
        user_id = await get_current_user_ws(ws)
        assert user_id == 42
