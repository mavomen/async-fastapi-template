"""Outgoing webhook dispatch and HMAC signature utilities."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.signing import build_signature_header, sign_payload, verify_signature_header
from app.events.base import Event
from app.notifications.crud.webhook import webhook as webhook_crud

logger = logging.getLogger("app.webhooks")

__all__ = ["build_signature_header", "sign_payload", "verify_signature_header"]


# -------- retry backoff --------
def compute_backoff(attempt: int) -> int:
    """Return the retry delay (seconds) for a 1-based attempt number.

    Exponential backoff: base * 2^(attempt - 1), capped at the configured maximum.
    """
    seconds = settings.WEBHOOK_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
    return int(min(seconds, settings.WEBHOOK_BACKOFF_MAX_SECONDS))


# -------- delivery payload --------
def build_delivery_payload(event: Event, delivery_id: int, attempt: int) -> dict[str, object]:
    """Build the JSON payload delivered to the webhook endpoint."""
    return {
        "id": event.id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "data": event.payload,
        "delivery_id": delivery_id,
        "attempt": attempt,
    }


@asynccontextmanager
async def _db_session() -> AsyncIterator[AsyncSession]:
    """Provide a writer session, initializing the session manager when needed."""
    from app.core.database import sessionmanager

    if sessionmanager._writer_engine is None:
        sessionmanager.init(settings.DATABASE_URL)
    async with sessionmanager.writer_session() as session:
        yield session


# -------- event-bus dispatcher --------
async def handle_event(event: Event) -> None:
    """EventBus handler: enqueue a delivery for every matching active webhook.

    Never raises — a webhook dispatch failure must not break the event-bus
    consumer loop or poison message acknowledgements.
    """
    if not settings.WEBHOOK_ENABLED:
        return
    try:
        async with _db_session() as db:
            if event.user_id is not None:
                from app.notifications.services.notifications import channel_enabled

                if not await channel_enabled(db, user_id=event.user_id, channel="webhook"):
                    logger.debug(
                        "Webhook dispatch skipped: webhook channel disabled",
                        extra={"event_id": event.id, "user_id": event.user_id},
                    )
                    return
            webhooks = await webhook_crud.get_active_for_event_type(db, event_type=event.event_type)
            for webhook in webhooks:
                delivery = await webhook_crud.create_delivery(
                    db,
                    webhook_id=webhook.id,
                    event=event,
                    max_attempts=settings.WEBHOOK_MAX_RETRIES + 1,
                )
                try:
                    from app.notifications.tasks.webhook import deliver_webhook

                    deliver_webhook.delay(delivery.id)
                except Exception:
                    logger.exception(
                        "Failed to enqueue webhook delivery",
                        extra={"delivery_id": delivery.id},
                    )
    except Exception:
        logger.exception("Webhook dispatch failed", extra={"event_id": event.id})
