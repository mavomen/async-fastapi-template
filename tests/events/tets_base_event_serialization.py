"""Test Event serialization roundtrip."""

from app.events.base import Event


def test_event_to_json_from_json():
    event = Event(event_type="test.test", payload={"key": "value"})
    json_data = event.to_json()
    restored = Event.from_json(json_data)
    assert restored.event_type == "test.test"
    assert restored.payload == {"key": "value"}
    assert restored.id == event.id
