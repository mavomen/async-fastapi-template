"""Tests for notification service helpers."""

import json

import pytest

from app.events.base import Event
from app.notifications.services.notifications import _payload_str, _push_websocket


class TestPayloadStr:
    def test_returns_payload_value(self):
        assert _payload_str({"title": "Hello"}, "title", "fallback") == "Hello"

    def test_falls_back_when_missing(self):
        assert _payload_str({}, "title", "fallback") == "fallback"

    def test_falls_back_when_none(self):
        assert _payload_str({"title": None}, "title", "fallback") == "fallback"

    def test_coerces_non_string(self):
        assert _payload_str({"title": 42}, "title", "fallback") == "42"


class TestPushWebSocket:
    @pytest.mark.asyncio
    async def test_sends_message_to_user(self, mocker):
        manager_mock = mocker.patch("app.websocket.manager.manager", autospec=True)
        event = Event(event_type="user.created", user_id=5)

        await _push_websocket(user_id=5, event=event, title="Welcome", body="Hi")

        assert manager_mock.send_personal_message.await_count == 1
        args = manager_mock.send_personal_message.await_args
        assert args.args[1] == "5"
        payload = json.loads(args.args[0])
        assert payload["type"] == "notification"
        assert payload["notification"]["id"] == event.id
        assert payload["notification"]["title"] == "Welcome"
        assert payload["notification"]["body"] == "Hi"

    @pytest.mark.asyncio
    async def test_never_raises_on_failure(self, mocker):
        manager_mock = mocker.patch("app.websocket.manager.manager", autospec=True)
        manager_mock.send_personal_message.side_effect = RuntimeError("ws down")

        await _push_websocket(
            user_id=5,
            event=Event(event_type="user.created", user_id=5),
            title="Welcome",
            body=None,
        )
