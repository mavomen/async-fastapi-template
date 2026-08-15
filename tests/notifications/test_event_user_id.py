"""Tests for the Event.user_id field serialization."""

import json

from app.events.base import Event


class TestEventUserId:
    def test_default_user_id_is_none(self):
        assert Event(event_type="user.created").user_id is None

    def test_to_json_includes_user_id(self):
        event = Event(event_type="user.created", payload={"id": 1}, user_id=42)
        data = json.loads(event.to_json())
        assert data["user_id"] == 42

    def test_from_json_restores_user_id(self):
        payload = json.dumps(
            {
                "id": "evt-1",
                "event_type": "user.created",
                "payload": {},
                "timestamp": "2026-01-01T00:00:00Z",
                "user_id": 7,
            }
        )
        assert Event.from_json(payload).user_id == 7

    def test_from_json_defaults_user_id_to_none(self):
        payload = json.dumps(
            {
                "id": "evt-1",
                "event_type": "user.created",
                "payload": {},
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        assert Event.from_json(payload).user_id is None

    def test_round_trip_preserves_user_id(self):
        original = Event(event_type="user.created", user_id=99)
        restored = Event.from_json(original.to_json())
        assert restored.user_id == 99
