"""Integration tests for the Celery webhook task DB internals (real Postgres)."""

import pytest

from app.core.database import sessionmanager
from app.models.webhook import Webhook, WebhookDelivery
from app.tasks.webhook import _load_delivery_and_webhook, _record_delivery_outcome, _run_async


def _make_webhook(session, **overrides) -> Webhook:
    webhook = Webhook(
        name="integration",
        url="https://example.com/hook",
        secret="s3cret",
        event_types=None,
        is_active=True,
        failure_count=0,
    )
    for key, value in overrides.items():
        setattr(webhook, key, value)
    session.add(webhook)
    return webhook


def _make_delivery(session, webhook_id: int, **overrides) -> WebhookDelivery:
    delivery = WebhookDelivery(
        webhook_id=webhook_id,
        event_id="evt-int",
        event_type="user.created",
        payload={"id": 1},
        attempt=0,
        max_attempts=3,
        status="pending",
    )
    for key, value in overrides.items():
        setattr(delivery, key, value)
    session.add(delivery)
    return delivery


def test_run_async_executes_coroutine():
    assert _run_async(_async_identity(7)) == 7


async def _async_identity(value: int) -> int:
    return value


@pytest.mark.asyncio
async def test_load_delivery_and_webhook(db_session):
    webhook = _make_webhook(db_session)
    db_session.add(webhook)
    await db_session.flush()
    delivery = _make_delivery(db_session, webhook_id=webhook.id)
    db_session.add(delivery)
    await db_session.commit()

    pair = await _load_delivery_and_webhook(delivery.id)
    assert pair is not None
    loaded_delivery, loaded_webhook = pair
    assert loaded_delivery.id == delivery.id
    assert loaded_webhook.id == webhook.id


@pytest.mark.asyncio
async def test_load_delivery_and_webhook_missing(db_session):
    assert await _load_delivery_and_webhook(999999) is None


@pytest.mark.asyncio
async def test_record_delivered_outcome_rolls_up(db_session):
    webhook = _make_webhook(db_session)
    db_session.add(webhook)
    await db_session.flush()
    delivery = _make_delivery(db_session, webhook_id=webhook.id)
    db_session.add(delivery)
    await db_session.commit()

    await _record_delivery_outcome(
        delivery.id,
        attempt=1,
        outcome={
            "status": "delivered",
            "response_status": 200,
            "response_body": "ok",
        },
    )

    from sqlalchemy import select

    async with sessionmanager.reader_session() as fresh:
        loaded_delivery = (
            await fresh.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery.id))
        ).scalar_one()
        loaded_webhook = (
            await fresh.execute(select(Webhook).where(Webhook.id == webhook.id))
        ).scalar_one()

    assert loaded_delivery.status == "delivered"
    assert loaded_delivery.attempt == 1
    assert loaded_delivery.response_status == 200
    assert loaded_delivery.response_body == "ok"
    assert loaded_delivery.delivered_at is not None
    assert loaded_webhook.last_status == "delivered"
    assert loaded_webhook.last_delivery_at is not None
    assert loaded_webhook.failure_count == 0


@pytest.mark.asyncio
async def test_record_failed_outcome_increments_failure_count(db_session):
    webhook = _make_webhook(db_session)
    db_session.add(webhook)
    await db_session.flush()
    delivery = _make_delivery(db_session, webhook_id=webhook.id)
    db_session.add(delivery)
    await db_session.commit()

    await _record_delivery_outcome(
        delivery.id,
        attempt=2,
        outcome={
            "status": "failed",
            "error": "HTTP 500",
            "next_retry_at": None,
        },
    )

    from sqlalchemy import select

    async with sessionmanager.writer_session() as fresh:
        loaded_delivery = (
            await fresh.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery.id))
        ).scalar_one()
        loaded_webhook = (
            await fresh.execute(select(Webhook).where(Webhook.id == webhook.id))
        ).scalar_one()

    assert loaded_delivery.status == "failed"
    assert loaded_delivery.attempt == 2
    assert loaded_delivery.error == "HTTP 500"
    assert loaded_delivery.delivered_at is None
    assert loaded_webhook.last_status == "failed"
    assert loaded_webhook.failure_count == 1


@pytest.mark.asyncio
async def test_record_outcome_missing_delivery_is_noop(db_session):
    await _record_delivery_outcome(
        999999,
        attempt=1,
        outcome={"status": "failed", "error": "boom"},
    )
