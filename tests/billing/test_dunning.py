"""Dunning: backoff units, real-Postgres schedule lifecycle, recovery."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models.subscription import SubscriptionStatus
from app.billing.services import dunning as dunning_service
from app.billing.services.invoicing import generate_invoice, issue, mark_paid
from app.identity.models.user import User
from tests.billing.test_subscription_lifecycle import (
    make_plan_row,
    make_subscription,
    make_tenant_row,
)

NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Pure units
# ---------------------------------------------------------------------------


class TestBackoff:
    def test_first_attempt_is_base(self):
        assert dunning_service.backoff_delay(1, base_minutes=60) == timedelta(hours=1)

    def test_exponential_growth(self):
        assert dunning_service.backoff_delay(3, base_minutes=60) == timedelta(hours=4)

    def test_capped_at_seven_days(self):
        assert dunning_service.backoff_delay(10, base_minutes=60) == timedelta(days=7)


def patched_settings(monkeypatch, max_attempts: int = 4):
    from app.core import config

    s = config.Settings(
        ENVIRONMENT="test",
        SECRET_KEY="a" * 32,
        DUNNING_MAX_ATTEMPTS=max_attempts,
        DUNNING_BASE_DELAY_MINUTES=60,
    )
    monkeypatch.setattr(dunning_service, "settings", s)
    return s


class TestResetDunning:
    def test_noop_when_clean(self):
        sub = make_subscription(1, 7)
        sub.failed_payment_count = 0
        sub.next_retry_at = None
        assert dunning_service.reset_dunning(sub) is False
        assert sub.failed_payment_count == 0

    def test_clears_all_state(self):
        sub = make_subscription(1, 7)
        sub.failed_payment_count = 3
        sub.last_payment_failure_at = NOW
        sub.next_retry_at = NOW
        assert dunning_service.reset_dunning(sub) is True
        assert sub.failed_payment_count == 0
        assert sub.last_payment_failure_at is None
        assert sub.next_retry_at is None


# ---------------------------------------------------------------------------
# Real-Postgres lifecycle
# ---------------------------------------------------------------------------


async def make_user_row(db: AsyncSession, tenant_id: int, email: str) -> int:
    user = User(
        email=email,
        username=email.split("@")[0] + str(tenant_id),
        hashed_password="x",
        tenant_id=tenant_id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user.id


def make_bus():
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


async def make_sub_with_tenant(db_session, name: str):
    tenant_id = await make_tenant_row(db_session, name=name)
    plan = await make_plan_row(db_session)
    sub = make_subscription(plan.id, tenant_id)
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


@pytest.mark.asyncio
async def test_record_failure_transitions_and_schedules(db_session, monkeypatch):
    patched_settings(monkeypatch)
    sub = await make_sub_with_tenant(db_session, "dun-co")

    bus = make_bus()
    await dunning_service.record_payment_failure(db_session, bus, sub, when=NOW)

    assert sub.status == SubscriptionStatus.PAST_DUE
    assert sub.failed_payment_count == 1
    assert sub.last_payment_failure_at == NOW
    assert sub.next_retry_at == NOW + timedelta(hours=1)
    bus.publish.assert_not_awaited()  # no users in this tenant yet


@pytest.mark.asyncio
async def test_record_failure_publishes_per_recipient(db_session, monkeypatch):
    patched_settings(monkeypatch)
    sub = await make_sub_with_tenant(db_session, "fanout-co")
    await make_user_row(db_session, sub.tenant_id, "owner@fanout.test")
    await make_user_row(db_session, sub.tenant_id, "second@fanout.test")

    bus = make_bus()
    await dunning_service.record_payment_failure(db_session, bus, sub, when=NOW)

    assert bus.publish.await_count == 2
    event = bus.publish.await_args_list[0].args[0]
    assert event.event_type == "billing.dunning.payment_failed"
    assert event.user_id is not None
    assert event.payload["failed_payment_count"] == 1


@pytest.mark.asyncio
async def test_sweep_reminds_then_suspends(db_session, monkeypatch):
    from app.billing.services.dunning import process_due_retries

    patched_settings(monkeypatch, max_attempts=2)
    sub = await make_sub_with_tenant(db_session, "sweep-co")
    await make_user_row(db_session, sub.tenant_id, "u@sweep.test")

    bus = make_bus()
    await dunning_service.record_payment_failure(db_session, bus, sub, when=NOW)
    await db_session.commit()
    stats = await process_due_retries(db_session, bus, now=NOW + timedelta(hours=2))
    assert stats["reminded"] == 1
    assert sub.status == SubscriptionStatus.PAST_DUE
    assert sub.failed_payment_count == 2
    reminder_event = bus.publish.await_args_list[-1].args[0]
    assert reminder_event.event_type == "billing.dunning.payment_reminder"

    stats = await process_due_retries(db_session, bus, now=NOW + timedelta(hours=6))
    await db_session.commit()
    assert stats["suspended"] == 1
    assert sub.status == SubscriptionStatus.SUSPENDED
    assert sub.suspended_at is not None
    suspended_event = bus.publish.await_args_list[-1].args[0]
    assert suspended_event.event_type == "billing.dunning.suspended"


@pytest.mark.asyncio
async def test_sweep_is_idempotent_between_slots(db_session, monkeypatch):
    from app.billing.services.dunning import process_due_retries

    patched_settings(monkeypatch, max_attempts=5)
    sub = await make_sub_with_tenant(db_session, "idem-co")

    bus = make_bus()
    await dunning_service.record_payment_failure(db_session, bus, sub, when=NOW)
    await db_session.commit()
    first = await process_due_retries(db_session, bus, now=NOW + timedelta(hours=2))
    await db_session.commit()  # the celery task owns this commit
    second = await process_due_retries(db_session, bus, now=NOW + timedelta(hours=2))
    assert first["reminded"] == 1
    assert second["due"] == 0


@pytest.mark.asyncio
async def test_mark_paid_recovers_past_due_subscription(db_session, monkeypatch):
    patched_settings(monkeypatch)
    sub = await make_sub_with_tenant(db_session, "recover-co")
    await make_user_row(db_session, sub.tenant_id, "u@recover.test")

    from app.billing.crud.plan import plan as crud_plan

    plan = await crud_plan.get(db_session, sub.plan_id)
    inv = await generate_invoice(db_session, sub, plan)
    await issue(db_session, inv.id)
    bus = make_bus()
    await dunning_service.record_payment_failure(db_session, bus, sub, when=NOW)
    await db_session.commit()
    assert sub.status == SubscriptionStatus.PAST_DUE

    await mark_paid(db_session, inv.id, bus)
    await db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.failed_payment_count == 0
    assert sub.next_retry_at is None
    types = [call.args[0].event_type for call in bus.publish.await_args_list]
    assert types[-1] == "billing.dunning.recovered"


@pytest.mark.asyncio
async def test_mark_paid_without_dunning_publishes_nothing_extra(db_session):
    sub = await make_sub_with_tenant(db_session, "clean-co")
    from app.billing.crud.plan import plan as crud_plan

    plan = await crud_plan.get(db_session, sub.plan_id)
    inv = await generate_invoice(db_session, sub, plan)
    await issue(db_session, inv.id)
    bus = make_bus()
    await mark_paid(db_session, inv.id, bus)
    types = [call.args[0].event_type for call in bus.publish.await_args_list]
    assert "billing.dunning.recovered" not in types


@pytest.mark.asyncio
async def test_suspended_is_not_live(db_session):
    from app.billing.crud.subscription import subscription as crud_subscription

    sub = await make_sub_with_tenant(db_session, "term-co")
    assert sub.is_live() is True

    sub.status = SubscriptionStatus.SUSPENDED
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    assert sub.is_live() is False
    assert await crud_subscription.get_live_for_tenant(db_session, sub.tenant_id) is None


@pytest.mark.asyncio
async def test_resolve_recipients_filters_inactive(db_session):
    tenant_id = await make_tenant_row(db_session, name="recip-co")
    active_id = await make_user_row(db_session, tenant_id, "a@recip.test")
    inactive = User(
        email="b@recip.test",
        username="b" + str(tenant_id),
        hashed_password="x",
        tenant_id=tenant_id,
        is_active=False,
    )
    db_session.add(inactive)
    await db_session.commit()

    recipients = await dunning_service.resolve_recipients(db_session, tenant_id)
    assert recipients == [active_id]


def test_task_disabled_flag_short_circuits(monkeypatch):
    from app.core import config
    from app.tasks.dunning import process_dunning

    s = config.Settings(ENVIRONMENT="test", SECRET_KEY="a" * 32, BILLING_DUNNING_ENABLED=False)
    monkeypatch.setattr("app.tasks.dunning.settings", s)
    result = process_dunning()
    assert result["disabled"] == 1
    assert result["reminded"] == 0
