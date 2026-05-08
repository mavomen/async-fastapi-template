"""Event publishing endpoint."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_event_bus
from app.events.base import Event, EventBus

router = APIRouter()


class EventPublishRequest(BaseModel):
    event_type: str
    payload: dict = {}


@router.post("/publish")
async def publish_event(
    req: EventPublishRequest,
    bus: EventBus = Depends(get_event_bus),
):
    """Publish an event to the event bus."""
    event = Event(event_type=req.event_type, payload=req.payload)
    await bus.publish(event)
    return {"id": event.id, "event_type": event.event_type, "status": "published"}
