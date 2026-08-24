"""Dunning: payment-failure retry schedule, reminders, and suspension.

The schedule is a simple position counter on the subscription
(``failed_payment_count``). Both real failures (recorded via
:func:`record_payment_failure`, e.g. from the Stripe
``invoice.payment_failed`` handler) and sweep ticks that come due
without a success advance the position, so the schedule terminates even
if no further webhooks arrive:

    failure N -> next action at now + delay(N)
    delay(N)  = base * 2**(N - 1), capped at 7 days

Sweep ticks publish ``billing.dunning.payment_reminder`` and consume one
schedule position; once the position reaches ``DUNNING_MAX_ATTEMPTS`` the
subscription is suspended (terminal) and ``billing.dunning.suspended``
is published. Recovery (a successful payment while past_due) resets all
dunning state; suspension itself is not reversible through this service
— the tenant starts a new subscription.

Events are fanned out to every active user of the subscription's tenant
and flow through the normal notifications pipeline (in-app + email,
per-user channel gating).
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models.subscription import Subscription, SubscriptionStatus
from app.billing.services import billing as billing_service
from app.core.config import settings
from app.events.base import Event, EventBus
from app.identity.models.user import User

logger = logging.getLogger("app.billing.dunning")

#: Upper bound for a single backoff step.
MAX_DELAY = timedelta(days=7)


def backoff_delay(attempt: int, *, base_minutes: int | None = None) -> timedelta:
    """Exponential backoff for schedule position ``attempt`` (1-based)."""
    base = base_minutes if base_minutes is not None else settings.DUNNING_BASE_DELAY_MINUTES
    capped_base = min(base * (2 ** max(0, attempt - 1)), MAX_DELAY.total_seconds() / 60)
    return timedelta(minutes=int(capped_base))


def is_dunning(sub: Subscription) -> bool:
    """True when the subscription carries unresolved dunning state."""
    return sub.failed_payment_count > 0 or sub.status == SubscriptionStatus.PAST_DUE


def reset_dunning(sub: Subscription) -> bool:
    """Clear dunning state in place. Returns True when something changed."""
    if sub.failed_payment_count == 0 and sub.next_retry_at is None:
        sub.last_payment_failure_at = None
        return False
    sub.failed_payment_count = 0
    sub.last_payment_failure_at = None
    sub.next_retry_at = None
    return True


async def resolve_recipients(db: AsyncSession, tenant_id: int | None) -> list[int]:
    """Active user ids belonging to the subscription's tenant."""
    if tenant_id is None:
        return []
    stmt = select(User.id).where(User.tenant_id == tenant_id, User.is_active.is_(True))
    rows = await db.execute(stmt)
    return [int(uid) for uid in rows.scalars().all()]


def dunning_event(suffix: str, sub: Subscription, user_id: int | None) -> Event:
    """Build a ``billing.dunning.<suffix>`` event for one recipient."""
    return Event(
        event_type=f"billing.dunning.{suffix}",
        payload={
            "subscription_id": sub.id,
            "tenant_id": sub.tenant_id,
            "plan_id": sub.plan_id,
            "status": str(sub.status),
            "failed_payment_count": sub.failed_payment_count,
        },
        user_id=user_id,
    )


async def _publish_to_recipients(
    bus: EventBus | None, db: AsyncSession, suffix: str, sub: Subscription
) -> int:
    """Publish one event per active tenant user. Returns recipient count.

    A ``None`` bus skips publishing (callers without an event context).
    """
    if bus is None:
        return 0
    recipients = await resolve_recipients(db, sub.tenant_id)
    for uid in recipients:
        await bus.publish(dunning_event(suffix, sub, uid))
    return len(recipients)


async def record_payment_failure(
    db: AsyncSession,
    bus: EventBus | None,
    sub: Subscription,
    *,
    when: datetime | None = None,
) -> Subscription:
    """Record a failed payment: advance the schedule and notify the tenant.

    Transitions the subscription to ``past_due`` first when needed.
    Caller owns the commit.
    """
    now = when or datetime.now(UTC)
    if sub.status != SubscriptionStatus.PAST_DUE:
        billing_service.assert_transition(sub.status, SubscriptionStatus.PAST_DUE)
        sub.status = SubscriptionStatus.PAST_DUE

    sub.failed_payment_count += 1
    sub.last_payment_failure_at = now
    sub.next_retry_at = now + backoff_delay(sub.failed_payment_count)
    db.add(sub)

    sent = await _publish_to_recipients(bus, db, "payment_failed", sub)
    logger.info(
        "payment failure recorded: subscription=%s attempt=%s next_retry=%s recipients=%s",
        sub.id,
        sub.failed_payment_count,
        sub.next_retry_at,
        sent,
    )
    return sub


async def suspend_subscription(
    db: AsyncSession, bus: EventBus | None, sub: Subscription
) -> Subscription:
    """Terminal suspension after the retry schedule is exhausted."""
    if sub.status != SubscriptionStatus.SUSPENDED:
        billing_service.assert_transition(sub.status, SubscriptionStatus.SUSPENDED)
        sub.status = SubscriptionStatus.SUSPENDED
        sub.suspended_at = datetime.now(UTC)
        sub.next_retry_at = None
        db.add(sub)
        await _publish_to_recipients(bus, db, "suspended", sub)
        logger.warning("subscription suspended: id=%s", sub.id)
    return sub


async def recover_subscription(
    db: AsyncSession, bus: EventBus | None, sub: Subscription
) -> Subscription:
    """Return a past_due subscription to active and clear dunning state."""
    if sub.status == SubscriptionStatus.PAST_DUE:
        billing_service.assert_transition(sub.status, SubscriptionStatus.ACTIVE)
        sub.status = SubscriptionStatus.ACTIVE
    had_dunning = reset_dunning(sub)
    if had_dunning or sub.status == SubscriptionStatus.ACTIVE:
        db.add(sub)
        await _publish_to_recipients(bus, db, "recovered", sub)
    return sub


async def process_due_retries(
    db: AsyncSession,
    bus: EventBus | None,
    *,
    now: datetime | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    """Advance every due dunning schedule by one tick.

    A due tick either fires a reminder (consuming one schedule position)
    or suspends the subscription when the positions are exhausted.
    Idempotent per tick: processed subs move strictly forward in the
    schedule or reach a terminal state. Caller owns the commit.
    """
    now = now or datetime.now(UTC)
    max_attempts = settings.DUNNING_MAX_ATTEMPTS
    stmt = (
        select(Subscription)
        .where(
            Subscription.status == SubscriptionStatus.PAST_DUE,
            Subscription.next_retry_at.is_not(None),
            Subscription.next_retry_at <= now,
        )
        .order_by(Subscription.id)
    )
    if limit is not None:
        stmt = stmt.limit(limit)

    subs = (await db.execute(stmt)).scalars().all()
    reminded = suspended = failed = 0
    for sub in subs:
        try:
            if sub.failed_payment_count >= max_attempts:
                await suspend_subscription(db, bus, sub)
                suspended += 1
            else:
                sub.failed_payment_count += 1
                sub.next_retry_at = now + backoff_delay(sub.failed_payment_count)
                db.add(sub)
                await _publish_to_recipients(bus, db, "payment_reminder", sub)
                reminded += 1
        except Exception:
            failed += 1
            logger.exception("dunning tick failed for subscription %s", sub.id)
    return {"due": len(subs), "reminded": reminded, "suspended": suspended, "failed": failed}
