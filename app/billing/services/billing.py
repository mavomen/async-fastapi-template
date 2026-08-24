"""Subscription lifecycle service.

Pure domain logic for the subscription state machine, billing-period
math, and hybrid proration:

- upgrades (higher price) apply immediately; unused time on the old plan
  is credited against the prorated charge for the new plan;
- downgrades (lower or equal price) are scheduled: they take effect at
  the end of the current period via ``pending_plan_id``.

All money is integer minor units. All functions are pure unless they
take a session; no I/O happens here except event publication through the
injected EventBus.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.billing.models.plan import Plan, PlanInterval
from app.billing.models.subscription import Subscription, SubscriptionStatus
from app.events.base import Event

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS: dict[SubscriptionStatus, frozenset[SubscriptionStatus]] = {
    SubscriptionStatus.TRIALING: frozenset(
        {SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELED}
    ),
    SubscriptionStatus.ACTIVE: frozenset(
        {SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELED}
    ),
    SubscriptionStatus.PAST_DUE: frozenset(
        {SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELED}
    ),
    SubscriptionStatus.CANCELED: frozenset(),
}


class IllegalTransitionError(Exception):
    """Raised when a status transition is not allowed."""

    def __init__(self, current: SubscriptionStatus, target: SubscriptionStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Illegal subscription transition: {current} -> {target}")


def assert_transition(current: SubscriptionStatus, target: SubscriptionStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise IllegalTransitionError(current, target)


# ---------------------------------------------------------------------------
# Period math
# ---------------------------------------------------------------------------

INTERVAL_DELTA: dict[PlanInterval, timedelta] = {
    PlanInterval.MONTHLY: timedelta(days=30),
    PlanInterval.YEARLY: timedelta(days=365),
}


def next_period_end(plan: Plan, start: datetime) -> datetime:
    return start + INTERVAL_DELTA[plan.interval]


def fraction_remaining(period_start: datetime, period_end: datetime, now: datetime) -> float:
    """Fraction of the billing period still unelapsed at ``now`` (clamped to [0, 1])."""
    total = (period_end - period_start).total_seconds()
    if total <= 0:
        return 0.0
    remaining = (period_end - now).total_seconds()
    return max(0.0, min(1.0, remaining / total))


# ---------------------------------------------------------------------------
# Proration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanChangePreview:
    credit_cents: int
    charge_cents: int
    net_cents: int


@dataclass(frozen=True)
class PlanChangeDecision:
    effective: str  # "immediate" | "scheduled"
    preview: PlanChangePreview | None
    pending_plan_id: int | None


def compute_unused_credit(plan: Plan, sub: Subscription, now: datetime) -> int:
    """Credit for the unelapsed portion of the current period."""
    frac = fraction_remaining(sub.current_period_start, sub.current_period_end, now)
    return round(plan.price_cents * frac)


def compute_prorated_charge(plan: Plan, start: datetime, end: datetime, now: datetime) -> int:
    """Charge for the unelapsed portion of a period at the new plan's price."""
    frac = fraction_remaining(start, end, now)
    return round(plan.price_cents * frac)


def decide_plan_change(
    current_plan: Plan,
    new_plan: Plan,
    sub: Subscription,
    now: datetime,
) -> PlanChangeDecision:
    """Hybrid proration policy.

    Upgrade (strictly higher price): immediate — credit unused old-plan time,
    charge prorated new-plan amount.
    Downgrade or equal price: scheduled at period end (no money movement).
    """
    if new_plan.currency != current_plan.currency:
        raise ValueError("cannot change plans across currencies")
    if new_plan.price_cents > current_plan.price_cents:
        credit = compute_unused_credit(current_plan, sub, now)
        charge = compute_prorated_charge(
            new_plan, sub.current_period_start, sub.current_period_end, now
        )
        return PlanChangeDecision(
            effective="immediate",
            preview=PlanChangePreview(
                credit_cents=credit, charge_cents=charge, net_cents=charge - credit
            ),
            pending_plan_id=None,
        )
    return PlanChangeDecision(effective="scheduled", preview=None, pending_plan_id=new_plan.id)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def subscription_event(event_suffix: str, sub: Subscription, user_id: int | None) -> Event:
    """Build a ``billing.subscription.<suffix>`` event carrying minimal payload."""
    return Event(
        event_type=f"billing.subscription.{event_suffix}",
        payload={
            "subscription_id": sub.id,
            "tenant_id": sub.tenant_id,
            "plan_id": sub.plan_id,
            "status": str(sub.status),
            "cancel_at_period_end": sub.cancel_at_period_end,
            "pending_plan_id": sub.pending_plan_id,
            "current_period_end": (
                sub.current_period_end.isoformat() if sub.current_period_end else None
            ),
        },
        user_id=user_id,
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
