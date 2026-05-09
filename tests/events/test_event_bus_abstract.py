"""Cover abstract methods of EventBus (importability)."""

from app.events.base import EventBus


def test_event_bus_cannot_be_instantiated():
    """EventBus is abstract."""
    try:
        bus = EventBus()
        assert False, "Should have raised TypeError"
    except TypeError:
        pass
