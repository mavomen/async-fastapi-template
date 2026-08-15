"""Outgoing webhook dispatch and HMAC signature utilities."""

import hashlib
import hmac
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.webhook import webhook as webhook_crud
from app.events.base import Event

logger = logging.getLogger("app.webhooks")


# -------- HMAC signatures (Stripe-style: t=<ts>,v1=<hex>) --------
def sign_payload(body: bytes, secret: str, timestamp: int) -> str:
    """Sign a request body with HMAC-SHA256, binding it to a timestamp."""
    message = f"{timestamp}.{body.decode()}".encode()
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_signature_header(body: bytes, secret: str, timestamp: int) -> str:
    """Build the ``X-Webhook-Signature`` header value for a payload."""
    return f"t={timestamp},v1={sign_payload(body, secret, timestamp)}"


def verify_signature_header(
    body: bytes,
    secret: str,
    signature_header: str | None,
    *,
    tolerance_seconds: int | None = None,
) -> bool:
    """Verify a ``t=<ts>,v1=<sig>`` signature header, rejecting stale timestamps."""
    if not signature_header:
        return False
    parts: dict[str, str] = {}
    for item in signature_header.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
    timestamp_str = parts.get("t")
    signature = parts.get("v1")
    if not timestamp_str or not signature:
        return False
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False
    tolerance = (
        tolerance_seconds
        if tolerance_seconds is not None
        else settings.WEBHOOK_SIGNATURE_TOLERANCE_SECONDS
    )
    if abs(int(time.time()) - timestamp) > tolerance:
        return False
    expected = sign_payload(body, secret, timestamp)
    return hmac.compare_digest(expected, signature)


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
                from app.services.notifications import channel_enabled

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
                    from app.tasks.webhook import deliver_webhook

                    deliver_webhook.delay(delivery.id)
                except Exception:
                    logger.exception(
                        "Failed to enqueue webhook delivery",
                        extra={"delivery_id": delivery.id},
                    )
    except Exception:
        logger.exception("Webhook dispatch failed", extra={"event_id": event.id})
