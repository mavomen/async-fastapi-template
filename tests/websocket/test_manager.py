"""Tests for WebSocket ConnectionManager."""

from unittest.mock import AsyncMock

import pytest

from app.websocket.manager import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


@pytest.mark.asyncio
async def test_connect_adds_connection(manager):
    ws = AsyncMock()
    await manager.connect(ws, "user1")
    assert ws in manager.active_connections["user1"]


@pytest.mark.asyncio
async def test_disconnect_removes_connection(manager):
    ws = AsyncMock()
    await manager.connect(ws, "user1")
    manager.disconnect(ws, "user1")
    assert "user1" not in manager.active_connections


@pytest.mark.asyncio
async def test_broadcast_continues_on_failure(manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws1.send_text.side_effect = Exception("connection lost")
    await manager.connect(ws1, "user1")
    await manager.connect(ws2, "user2")

    await manager.broadcast("hello")

    ws2.send_text.assert_awaited_once_with("hello")
    assert ws1 not in manager.active_connections.get("user1", set())


@pytest.mark.asyncio
async def test_send_personal_removes_dead_connection(manager):
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws1.send_text.side_effect = Exception("dead")
    await manager.connect(ws1, "user1")
    await manager.connect(ws2, "user1")

    await manager.send_personal_message("hello", "user1")

    ws2.send_text.assert_awaited_once_with("hello")
    assert ws1 not in manager.active_connections["user1"]
    assert ws2 in manager.active_connections["user1"]


@pytest.mark.asyncio
async def test_broadcast_empty_does_not_error(manager):
    await manager.broadcast("hello")


@pytest.mark.asyncio
async def test_send_personal_no_user_does_not_error(manager):
    await manager.send_personal_message("hello", "nonexistent")
