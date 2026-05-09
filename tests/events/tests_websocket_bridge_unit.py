"""Unit test for the WebSocket event bridge."""

import pytest
from unittest.mock import AsyncMock, patch
from app.events.websocket_bridge import broadcast_event
from app.events.base import Event


@pytest.mark.asyncio
async def test_broadcast_event():
    with patch("app.events.websocket_bridge.manager.broadcast", new_callable=AsyncMock) as mock_broadcast:
        event = Event(event_type="test", payload={})
        await broadcast_event(event)
        mock_broadcast.assert_called_once()
