"""Unit tests for billing service: state machine, period math, proration."""

from datetime import UTC, datetime, timedelta

import pytest

from app.billing.models.plan import Plan, PlanInterval
from app.billing.models.subscription import Subscription, SubscriptionStatus
from app.billing.services import billing


def make_plan(**overrides) -> Plan:
    defaults = {
        "id": 1,
        "name": "Pro",
        "slug": "pro",
        "description": None,
        "price_cents": 4900,
        "currency": "usd",
        "interval": PlanInterval.MONTHLY,
        "trial_days": 0,
        "is_active": True,
    }
    return Plan(**{**defaults, **overrides})


def make_sub(plan: Plan, *, start=None, end=None, status=SubscriptionStatus.ACTIVE) -> Subscription:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    return Subscription(
        tenant_id=7,
        plan_id=plan.id,
        status=status,
        current_period_start=start or now,
        current_period_end=end or (start or now) + timedelta(days=30),
    )


class TestStateMachine:
    def test_legal_transitions_pass(self):
        billing.assert_transition(SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE)
        billing.assert_transition(SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE)
        billing.assert_transition(SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELED)

    def test_terminal_state_has_no_exits(self):
        with pytest.raises(billing.IllegalTransitionError):
            billing.assert_transition(SubscriptionStatus.CANCELED, SubscriptionStatus.ACTIVE)

    def test_active_to_trialing_illegal(self):
        with pytest.raises(billing.IllegalTransitionError):
            billing.assert_transition(SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)


class TestPeriodMath:
    def test_next_period_end_monthly(self):
        plan = make_plan(interval=PlanInterval.MONTHLY)
        start = datetime(2026, 8, 1, tzinfo=UTC)
        assert billing.next_period_end(plan, start) == start + timedelta(days=30)

    def test_next_period_end_yearly(self):
        plan = make_plan(interval=PlanInterval.YEARLY)
        start = datetime(2026, 8, 1, tzinfo=UTC)
        assert billing.next_period_end(plan, start) == start + timedelta(days=365)

    def test_fraction_remaining_midpoint(self):
        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = start + timedelta(days=30)
        mid = start + timedelta(days=15)
        assert billing.fraction_remaining(start, end, mid) == pytest.approx(0.5)

    def test_fraction_remaining_clamps(self):
        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = start + timedelta(days=30)
        after = end + timedelta(days=5)
        before = start - timedelta(days=5)
        assert billing.fraction_remaining(start, end, after) == 0.0
        assert billing.fraction_remaining(start, end, before) == 1.0

    def test_zero_length_period_is_zero(self):
        t = datetime(2026, 8, 1, tzinfo=UTC)
        assert billing.fraction_remaining(t, t, t) == 0.0


class TestProration:
    def test_unused_credit_halfway(self):
        plan = make_plan(price_cents=4900)
        sub = make_sub(plan)
        mid = sub.current_period_start + timedelta(days=15)
        assert billing.compute_unused_credit(plan, sub, mid) == 2450

    def test_prorated_charge_matches_credit_for_equal_price(self):
        plan = make_plan(price_cents=4900)
        sub = make_sub(plan)
        mid = sub.current_period_start + timedelta(days=10)
        credit = billing.compute_unused_credit(plan, sub, mid)
        charge = billing.compute_prorated_charge(
            plan, sub.current_period_start, sub.current_period_end, mid
        )
        assert credit == charge == round(4900 * 20 / 30)

    def test_upgrade_immediate_with_preview(self):
        old_plan = make_plan(id=1, slug="basic", price_cents=1000)
        new_plan = make_plan(id=2, slug="pro", price_cents=3000)
        sub = make_sub(old_plan)
        mid = sub.current_period_start + timedelta(days=15)

        decision = billing.decide_plan_change(old_plan, new_plan, sub, mid)

        assert decision.effective == "immediate"
        assert decision.pending_plan_id is None
        assert decision.preview is not None
        assert decision.preview.credit_cents == 500
        assert decision.preview.charge_cents == 1500
        assert decision.preview.net_cents == 1000

    def test_downgrade_scheduled_without_money_movement(self):
        old_plan = make_plan(id=1, slug="pro", price_cents=3000)
        new_plan = make_plan(id=2, slug="basic", price_cents=1000)
        sub = make_sub(old_plan)
        mid = sub.current_period_start + timedelta(days=15)

        decision = billing.decide_plan_change(old_plan, new_plan, sub, mid)

        assert decision.effective == "scheduled"
        assert decision.preview is None
        assert decision.pending_plan_id == new_plan.id

    def test_currency_mismatch_rejected(self):
        old_plan = make_plan(currency="usd")
        new_plan = make_plan(slug="eur-pro", currency="eur", price_cents=9999)
        sub = make_sub(old_plan)
        with pytest.raises(ValueError, match="currencies"):
            billing.decide_plan_change(old_plan, new_plan, sub, billing_service_now())


def billing_service_now() -> datetime:
    from datetime import timedelta

    base = datetime(2026, 8, 1, tzinfo=UTC)
    return base + timedelta(days=1)
