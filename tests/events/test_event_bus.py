"""Unit tests for Event and EventBus abstractions."""

import pytest

from app.events.base import Event, EventBus


def test_event_serialization():
    event = Event(event_type="user.created", payload={"user_id": 42})
    json_data = event.to_json()
    restored = Event.from_json(json_data)
    assert restored.event_type == "user.created"
    assert restored.payload == {"user_id": 42}


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    """Test that a simple in‑memory bus works for unit tests."""

    class InMemoryBus(EventBus):
        def __init__(self):
            self.handlers = {}
            self.published = []

        async def publish(self, event):
            self.published.append(event)
            for handler in self.handlers.get(event.event_type, []):
                await handler(event)

        async def subscribe(self, event_type, handler):
            self.handlers.setdefault(event_type, []).append(handler)

        async def unsubscribe(self, event_type, handler):
            self.handlers[event_type].remove(handler)

    bus = InMemoryBus()
    received = []

    async def handler(event: Event):
        received.append(event)

    await bus.subscribe("test", handler)
    event = Event(event_type="test", payload={"data": 1})
    await bus.publish(event)
    assert len(received) == 1
    assert received[0].payload == {"data": 1}
