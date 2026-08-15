"""Celery task that delivers webhook payloads with retry and exponential backoff."""

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.core.config import settings
from app.events.base import Event
from app.models.webhook import Webhook, WebhookDelivery
from app.services.webhook import (
    build_delivery_payload,
    build_signature_header,
    compute_backoff,
)
from app.tasks.base import BaseTask

logger = get_task_logger(__name__)

_STATUS_DELIVERED = "delivered"
_STATUS_FAILED = "failed"


def _run_async(coro: Any) -> Any:
    """Run an async coroutine to completion from a synchronous Celery worker."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _load_delivery_and_webhook(delivery_id: int) -> tuple[WebhookDelivery, Webhook] | None:
    from app.core.database import sessionmanager
    from app.crud.webhook import webhook as webhook_crud

    if sessionmanager._writer_engine is None:
        sessionmanager.init(settings.DATABASE_URL)
    async with sessionmanager.writer_session() as db:
        return await webhook_crud.get_delivery_with_webhook(db, delivery_id=delivery_id)


async def _record_delivery_outcome(
    delivery_id: int,
    *,
    attempt: int,
    outcome: dict[str, Any],
) -> None:
    """Persist a delivery attempt outcome and roll up the webhook summary."""
    from app.core.database import sessionmanager
    from app.crud.webhook import webhook as webhook_crud

    status = outcome["status"]
    if sessionmanager._writer_engine is None:
        sessionmanager.init(settings.DATABASE_URL)
    async with sessionmanager.writer_session() as db:
        pair = await webhook_crud.get_delivery_with_webhook(db, delivery_id=delivery_id)
        if pair is None:
            return
        delivery, webhook = pair
        now = datetime.now(UTC)
        delivery.attempt = attempt
        delivery.status = status
        delivery.error = outcome.get("error")
        delivery.response_status = outcome.get("response_status")
        delivery.response_body = outcome.get("response_body")
        delivery.next_retry_at = outcome.get("next_retry_at")
        delivery.delivered_at = now if status == _STATUS_DELIVERED else None
        webhook.last_delivery_at = now
        webhook.last_status = status
        if status == _STATUS_DELIVERED:
            webhook.failure_count = 0
        elif status == _STATUS_FAILED:
            webhook.failure_count += 1
        db.add(delivery)
        db.add(webhook)
        await db.commit()


def _perform_delivery(delivery: WebhookDelivery, webhook: Webhook) -> str:
    """POST the signed payload and record the outcome.

    Returns one of ``delivered``, ``failed``, ``retry``, or ``webhook-disabled``.
    """
    attempt = delivery.attempt + 1
    event = Event(
        event_type=delivery.event_type,
        payload=delivery.payload or {},
        id=delivery.event_id,
        timestamp=delivery.created_at.isoformat(),
    )
    body = json.dumps(
        build_delivery_payload(event, delivery.id, attempt), separators=(",", ":")
    ).encode("utf-8")
    timestamp = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "async-fastapi-template-webhook/1.0",
        "X-Webhook-Signature": build_signature_header(body, webhook.secret, timestamp),
        "X-Webhook-Event": delivery.event_type,
        "X-Webhook-Id": delivery.event_id,
        "X-Webhook-Delivery": str(delivery.id),
        "X-Webhook-Attempt": str(attempt),
    }

    try:
        with httpx.Client(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
            response = client.post(webhook.url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        will_retry = attempt < delivery.max_attempts
        _run_async(
            _record_delivery_outcome(
                delivery.id,
                attempt=attempt,
                outcome={
                    "status": "retrying" if will_retry else _STATUS_FAILED,
                    "error": str(exc),
                    "next_retry_at": (
                        datetime.now(UTC) + timedelta(seconds=compute_backoff(attempt))
                        if will_retry
                        else None
                    ),
                },
            )
        )
        return "retry" if will_retry else _STATUS_FAILED

    if 200 <= response.status_code < 300:
        _run_async(
            _record_delivery_outcome(
                delivery.id,
                attempt=attempt,
                outcome={
                    "status": _STATUS_DELIVERED,
                    "response_status": response.status_code,
                    "response_body": response.text[:1000],
                },
            )
        )
        return _STATUS_DELIVERED

    will_retry = attempt < delivery.max_attempts
    _run_async(
        _record_delivery_outcome(
            delivery.id,
            attempt=attempt,
            outcome={
                "status": "retrying" if will_retry else _STATUS_FAILED,
                "error": f"HTTP {response.status_code}",
                "response_status": response.status_code,
                "response_body": response.text[:1000],
                "next_retry_at": (
                    datetime.now(UTC) + timedelta(seconds=compute_backoff(attempt))
                    if will_retry
                    else None
                ),
            },
        )
    )
    return "retry" if will_retry else _STATUS_FAILED


@celery_app.task(bind=True, base=BaseTask, max_retries=settings.WEBHOOK_MAX_RETRIES)  # type: ignore[untyped-decorator]
def deliver_webhook(self: Any, delivery_id: int) -> str:
    """Deliver a single webhook delivery record, retrying with backoff on failure."""
    pair = _run_async(_load_delivery_and_webhook(delivery_id))
    if pair is None:
        return "not-found"
    delivery, webhook = pair

    if delivery.status == _STATUS_DELIVERED:
        return "already-delivered"

    if not webhook.is_active:
        _run_async(
            _record_delivery_outcome(
                delivery.id,
                attempt=delivery.attempt,
                outcome={"status": _STATUS_FAILED, "error": "webhook disabled"},
            )
        )
        return "webhook-disabled"

    outcome = _perform_delivery(delivery, webhook)
    if outcome == "retry":
        raise self.retry(
            exc=Exception(f"webhook delivery {delivery_id} failed"),
            countdown=compute_backoff(delivery.attempt + 1),
            max_retries=settings.WEBHOOK_MAX_RETRIES,
        )
    return outcome
