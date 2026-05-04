"""Tests for WebSocket chat endpoint."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_websocket_connect_and_chat(client: TestClient):
    """Connect with mocked auth, send message, receive broadcast."""
    mock_auth = AsyncMock(return_value=42)
    with patch("app.websocket.chat.get_current_user_ws", mock_auth):
        with client.websocket_connect("/ws/chat?token=fake") as websocket:
            websocket.send_text("Hello world")
            data = websocket.receive_text()
            assert "User 42: Hello world" in data
