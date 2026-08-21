"""Notification channel dispatch and per-user preference gating."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.notification import notification as notification_crud
from app.crud.notification import notification_preference as preference_crud
from app.events.base import Event
from app.identity.crud.user import user as user_crud
from app.models.notification_preference import NotificationPreference

logger = logging.getLogger("app.notifications")

Channel = Literal["email", "in_app", "webhook"]


@asynccontextmanager
async def _db_session() -> AsyncIterator[AsyncSession]:
    """Provide a writer session, initializing the session manager when needed."""
    from app.core.database import sessionmanager

    if sessionmanager._writer_engine is None:
        sessionmanager.init(settings.DATABASE_URL)
    async with sessionmanager.writer_session() as session:
        yield session


def _channel_enabled_for_preference(pref: NotificationPreference, channel: Channel) -> bool:
    if channel == "email":
        return pref.email_enabled
    if channel == "in_app":
        return pref.in_app_enabled
    return pref.webhook_enabled


async def channel_enabled(db: AsyncSession, *, user_id: int, channel: Channel) -> bool:
    """Return whether a user has the given channel enabled.

    Users without a preference row default to all channels enabled.
    """
    pref = await preference_crud.get_for_user(db, user_id=user_id)
    if pref is None:
        return True
    return _channel_enabled_for_preference(pref, channel)


def _payload_str(payload: dict[str, Any], key: str, default: str) -> str:
    value = payload.get(key)
    return default if value is None else str(value)


async def _push_websocket(*, user_id: int, event: Event, title: str, body: str | None) -> None:
    """Best-effort push to any live WebSocket sessions for the user."""
    try:
        from app.websocket.manager import manager

        message = json.dumps(
            {
                "type": "notification",
                "notification": {
                    "id": event.id,
                    "event_type": event.event_type,
                    "title": title,
                    "body": body,
                },
            }
        )
        await manager.send_personal_message(message, str(user_id))
    except Exception:
        logger.debug("WebSocket notification push failed", exc_info=True)


async def _create_in_app(db: AsyncSession, *, user_id: int, event: Event) -> None:
    title = _payload_str(event.payload, "title", event.event_type)
    body_value = event.payload.get("body")
    body = body_value if isinstance(body_value, str) else None
    notification = await notification_crud.create_for_user(
        db,
        user_id=user_id,
        event_type=event.event_type,
        title=title,
        body=body,
    )
    await _push_websocket(
        user_id=user_id, event=event, title=notification.title, body=notification.body
    )


async def _dispatch_email(db: AsyncSession, *, user_id: int, event: Event) -> None:
    user = await user_crud.get(db, id=user_id)
    if user is None or not user.email:
        return
    title = _payload_str(event.payload, "title", f"New {event.event_type} notification")
    body_value = event.payload.get("body")
    context: dict[str, Any] = {
        "title": title,
        "event_type": event.event_type,
    }
    if isinstance(body_value, str):
        context["body"] = body_value
    try:
        from app.services.email import send_email_with_retry

        send_email_with_retry.delay(
            user.email,
            title,
            "notification.html",
            context,
        )
    except Exception:
        logger.exception(
            "Failed to enqueue notification email",
            extra={"user_id": user_id},
        )


async def handle_notification_event(event: Event) -> None:
    """EventBus handler: dispatch an event to the in-app and email channels.

    Channel delivery respects per-user preferences and defaults to enabled.
    Never raises — a dispatch failure must not break the event-bus consumer
    loop or poison message acknowledgements.
    """
    if not settings.NOTIFICATION_ENABLED:
        return
    user_id = event.user_id
    if user_id is None:
        return
    try:
        async with _db_session() as db:
            if await channel_enabled(db, user_id=user_id, channel="in_app"):
                await _create_in_app(db, user_id=user_id, event=event)
            if await channel_enabled(db, user_id=user_id, channel="email"):
                await _dispatch_email(db, user_id=user_id, event=event)
    except Exception:
        logger.exception(
            "Notification dispatch failed",
            extra={"event_id": event.id, "user_id": user_id},
        )
