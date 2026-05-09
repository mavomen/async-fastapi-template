"""Celery task that bridges events to the WebSocket manager."""

from app.core.celery_app import celery_app
from app.events.base import Event
from app.events.websocket_bridge import broadcast_event


@celery_app.task(name="app.events.process_event")
def process_event(event_json: str) -> None:
    """
    Celery task that processes an event.
    Currently broadcasts it to WebSocket clients.
    """
    event = Event.from_json(event_json)
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(broadcast_event(event))
