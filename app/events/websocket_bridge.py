"""Bridge between EventBus and WebSocket manager."""

from app.events.base import Event
from app.websocket.manager import manager
import logging

logger = logging.getLogger("app.events.websocket")


async def broadcast_event(event: Event) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    message = f"event:{event.event_type}: {event.id}"
    await manager.broadcast(message)
    logger.debug("Event broadcast to WebSocket", extra={"event_type": event.event_type})
