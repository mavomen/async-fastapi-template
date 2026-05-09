"""Abstract event and event bus definitions."""

import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Event:
    """Base event with type, payload, and metadata."""

    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_json(self) -> str:
        return json.dumps(
            {
                "id": self.id,
                "event_type": self.event_type,
                "payload": self.payload,
                "timestamp": self.timestamp,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> "Event":
        obj = json.loads(data)
        return cls(
            event_type=obj["event_type"],
            payload=obj.get("payload", {}),
            id=obj["id"],
            timestamp=obj["timestamp"],
        )


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus(ABC):
    """Abstract event bus with publish/subscribe capabilities."""

    @abstractmethod
    async def connect(self) -> None:
        """Initialize the event bus connection."""
        ...

    @abstractmethod
    async def publish(self, event: Event) -> None:
        """Publish an event to the bus."""
        ...

    @abstractmethod
    async def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        ...

    @abstractmethod
    async def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler."""
        ...
