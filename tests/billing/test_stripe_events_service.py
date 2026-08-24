"""Unit tests for Stripe event processing (state machine mapping, idempotency)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.billing.models.subscription import SubscriptionStatus
from app.billing.services import billing as billing_service
from app.billing.services import stripe_events


def make_db(scalar=None):
    """MagicMock session whose execute().scalar_one_or_none() yields ``scalar``."""
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar)
    db.execute = AsyncMock(return_value=result)
    return db


# ---------------------------------------------------------------------------
# record_event idempotency ledger
# ---------------------------------------------------------------------------


class TestRecordEvent:
    @pytest.mark.asyncio
    async def test_first_delivery_is_fresh(self):
        db = make_db()
        assert await stripe_events.record_event(db, "evt_1", "checkout.session.completed") is True
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_seen_event_returns_false(self):
        seen = MagicMock()
        db = make_db(seen)
        assert await stripe_events.record_event(db, "evt_1", "x") is False
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_integrity_race_returns_false(self):
        db = make_db()
        db.commit = AsyncMock(side_effect=IntegrityError("dup", None, Exception()))
        assert await stripe_events.record_event(db, "evt_1", "x") is False
        db.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# Stripe status / period parsing
# ---------------------------------------------------------------------------


class TestStatusParsing:
    def test_direct_status_map(self):
        now = int(datetime.now(UTC).timestamp())
        for raw, expected in [
            ("active", SubscriptionStatus.ACTIVE),
            ("past_due", SubscriptionStatus.PAST_DUE),
            ("unpaid", SubscriptionStatus.PAST_DUE),
            ("canceled", SubscriptionStatus.CANCELED),
        ]:
            assert stripe_events._status_from_stripe({"status": raw, "trial_end": 0}) == expected, (
                raw
            )

    def test_trialing_with_future_trial_end(self):
        future = int((datetime.now(UTC) + timedelta(days=3)).timestamp())
        assert (
            stripe_events._status_from_stripe({"status": "trialing", "trial_end": future})
            == SubscriptionStatus.TRIALING
        )

    def test_expired_trial_maps_to_active(self):
        past = int((datetime.now(UTC) - timedelta(days=1)).timestamp())
        assert (
            stripe_events._status_from_stripe({"status": "trialing", "trial_end": past})
            == SubscriptionStatus.ACTIVE
        )

    def test_unmapped_status_raises(self):
        with pytest.raises(ValueError, match="unmapped"):
            stripe_events._status_from_stripe({"status": "incomplete_expired"})

    def test_period_defaults_when_missing(self):
        start, end = stripe_events._period_from_stripe({})
        assert end > start

    def test_period_from_unix_timestamps(self):
        now = int(datetime.now(UTC).timestamp())
        start, end = stripe_events._period_from_stripe(
            {"current_period_start": now, "current_period_end": now + 86_400}
        )
        assert (end - start).days == 1


# ---------------------------------------------------------------------------
# checkout.session.completed
# ---------------------------------------------------------------------------


CHECKOUT_EVENT = {
    "id": "cs_test",
    "metadata": {"tenant_id": "7", "plan_id": "1"},
    "subscription": "sub_123",
}


class TestCheckoutCompleted:
    @pytest.mark.asyncio
    async def test_missing_fields_skipped(self, mocker):
        mocker.patch("app.billing.crud.plan.plan.get", new=AsyncMock())
        db = make_db()
        outcome = await stripe_events.handle_checkout_completed(db, {"metadata": {}})
        assert outcome == "skipped"

    @pytest.mark.asyncio
    async def test_unknown_plan_skipped(self, mocker):
        mocker.patch("app.billing.crud.plan.plan.get", new=AsyncMock(return_value=None))
        db = make_db()
        assert await stripe_events.handle_checkout_completed(db, dict(CHECKOUT_EVENT)) == "skipped"

    @pytest.mark.asyncio
    async def test_creates_subscription(self, mocker):
        plan_row = MagicMock(id=1)
        mocker.patch("app.billing.crud.plan.plan.get", new=AsyncMock(return_value=plan_row))
        mocker.patch(
            "app.billing.crud.subscription.subscription.get_live_for_tenant",
            new=AsyncMock(return_value=None),
        )
        db = make_db()
        added = []
        db.add = lambda obj: added.append(obj)

        outcome = await stripe_events.handle_checkout_completed(
            db,
            {
                **CHECKOUT_EVENT,
                "stripe_subscription_object": {"id": "sub_123", "status": "active"},
            },
        )
        assert outcome == "created"
        assert len(added) == 1
        sub = added[0]
        assert sub.tenant_id == 7
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.stripe_subscription_id == "sub_123"
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_links_stripe_id_to_existing_local_sub(self, mocker):
        plan_row = MagicMock(id=1)
        existing = MagicMock(stripe_subscription_id=None)
        mocker.patch("app.billing.crud.plan.plan.get", new=AsyncMock(return_value=plan_row))
        mocker.patch(
            "app.billing.crud.subscription.subscription.get_live_for_tenant",
            new=AsyncMock(return_value=existing),
        )
        db = make_db()
        outcome = await stripe_events.handle_checkout_completed(db, dict(CHECKOUT_EVENT))
        assert outcome == "linked"
        assert existing.stripe_subscription_id == "sub_123"

    @pytest.mark.asyncio
    async def test_second_checkout_is_duplicate(self, mocker):
        plan_row = MagicMock(id=1)
        existing = MagicMock(stripe_subscription_id="sub_other")
        mocker.patch("app.billing.crud.plan.plan.get", new=AsyncMock(return_value=plan_row))
        mocker.patch(
            "app.billing.crud.subscription.subscription.get_live_for_tenant",
            new=AsyncMock(return_value=existing),
        )
        db = make_db()
        assert await stripe_events.handle_checkout_completed(db, dict(CHECKOUT_EVENT)) == (
            "duplicate"
        )


# ---------------------------------------------------------------------------
# customer.subscription.updated/deleted + invoice.payment_failed
# ---------------------------------------------------------------------------


def live_active_sub(stripe_id="sub_123"):
    sub = MagicMock()
    sub.stripe_subscription_id = stripe_id
    sub.status = SubscriptionStatus.ACTIVE
    sub.pending_plan_id = None
    sub.cancel_at_period_end = False
    sub.canceled_at = None
    sub.current_period_start = datetime.now(UTC)
    sub.current_period_end = datetime.now(UTC) + timedelta(days=15)
    return sub


class TestSubscriptionSync:
    @pytest.mark.asyncio
    async def test_unknown_stripe_id_ignored(self):
        db = make_db()
        assert await stripe_events.handle_subscription_sync(db, {"id": "sub_ghost"}) == "unknown"

    @pytest.mark.asyncio
    async def test_past_due_transition_applied(self):
        sub = live_active_sub()
        db = make_db(sub)
        outcome = await stripe_events.handle_subscription_sync(
            db, {"id": "sub_123", "status": "past_due"}
        )
        assert outcome == "synced"
        assert sub.status == SubscriptionStatus.PAST_DUE

    @pytest.mark.asyncio
    async def test_canceled_sets_terminal_state(self):
        sub = live_active_sub()
        db = make_db(sub)
        outcome = await stripe_events.handle_subscription_sync(
            db, {"id": "sub_123", "status": "canceled"}
        )
        assert outcome == "synced"
        assert sub.status == SubscriptionStatus.CANCELED
        assert sub.cancel_at_period_end is False
        assert sub.pending_plan_id is None

    @pytest.mark.asyncio
    async def test_deleted_event_forces_cancel(self):
        # execute() sequence: record_event -> sync lookup -> mark_processed
        sub = live_active_sub()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(side_effect=[None, sub, sub])
        db = make_db()
        db.execute = AsyncMock(return_value=result)
        outcome = await stripe_events.process_event(
            db,
            {
                "id": "evt_del",
                "type": "customer.subscription.deleted",
                "data": {"object": {"id": "sub_123"}},
            },
        )
        assert outcome == "synced"
        assert sub.status == SubscriptionStatus.CANCELED

    @pytest.mark.asyncio
    async def test_noop_when_status_matches(self):
        sub = live_active_sub()
        db = make_db(sub)
        outcome = await stripe_events.handle_subscription_sync(
            db, {"id": "sub_123", "status": "active"}
        )
        assert outcome == "unchanged"
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_illegal_transition_raises(self):
        sub = live_active_sub()
        sub.status = SubscriptionStatus.CANCELED
        db = make_db(sub)
        with pytest.raises(billing_service.IllegalTransitionError):
            await stripe_events.handle_subscription_sync(
                db, {"id": "sub_123", "status": "past_due"}
            )


class TestPaymentFailed:
    @pytest.mark.asyncio
    async def test_missing_subscription_field_skipped(self):
        db = make_db()
        assert await stripe_events.handle_payment_failed(db, {}) == "skipped"

    @pytest.mark.asyncio
    async def test_unknown_subscription_reported(self):
        db = make_db()
        assert await stripe_events.handle_payment_failed(db, {"subscription": "sub_x"}) == (
            "unknown"
        )

    @pytest.mark.asyncio
    async def test_drives_to_past_due(self):
        sub = live_active_sub()
        sub.failed_payment_count = 0
        db = make_db(sub)
        outcome = await stripe_events.handle_payment_failed(db, {"subscription": "sub_123"})
        assert outcome == "past_due"
        assert sub.status == SubscriptionStatus.PAST_DUE
        assert sub.failed_payment_count == 1
        assert sub.next_retry_at is not None

    @pytest.mark.asyncio
    async def test_repeated_failure_advances_schedule(self):
        sub = live_active_sub()
        sub.status = SubscriptionStatus.PAST_DUE
        sub.failed_payment_count = 1
        db = make_db(sub)
        assert await stripe_events.handle_payment_failed(db, {"subscription": "sub_123"}) == (
            "past_due"
        )
        assert sub.failed_payment_count == 2


# ---------------------------------------------------------------------------
# Full dispatch pipeline
# ---------------------------------------------------------------------------


class TestProcessEventPipeline:
    @pytest.mark.asyncio
    async def test_marks_processed_after_success(self, mocker):
        from app.billing.models.stripe_event import StripeEvent

        mocker.patch(
            "app.billing.crud.subscription.subscription.get_live_for_tenant",
            new=AsyncMock(return_value=None),
        )
        mocker.patch("app.billing.crud.plan.plan.get", new=AsyncMock(return_value=None))
        # execute() sequence: record_event -> payment_failed lookup -> mark_processed
        ledger_row = StripeEvent(event_id="evt_pipe", event_type="invoice.payment_failed")
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(side_effect=[None, None, ledger_row])
        db = make_db()
        db.execute = AsyncMock(return_value=result)

        event = {
            "id": "evt_pipe",
            "type": "invoice.payment_failed",
            "data": {"object": {"subscription": "sub_zzz"}},
        }
        outcome = await stripe_events.process_event(db, event)
        assert outcome == "unknown"  # unknown local subscription...
        assert ledger_row.processed_at is not None  # ...but event still marked processed

    @pytest.mark.asyncio
    async def test_unrecognized_type_is_ignored_but_recorded(self):
        ledger_row = stripe_events.StripeEvent(event_id="evt_u", event_type="payout.created")
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(side_effect=[None, ledger_row])
        db = make_db()
        db.execute = AsyncMock(return_value=result)
        outcome = await stripe_events.process_event(
            db,
            {"id": "evt_u", "type": "payout.created", "data": {"object": {}}},
        )
        assert outcome == "ignored"
        assert ledger_row.processed_at is not None
