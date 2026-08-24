"""Idempotent processing of inbound Stripe webhook events.

Pipeline: signature already verified at the endpoint layer -> record the
event id (unique constraint = idempotency gate) -> apply domain changes
through the existing subscription state machine.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.crud.plan import plan as crud_plan
from app.billing.crud.subscription import subscription as crud_subscription
from app.billing.models.stripe_event import StripeEvent
from app.billing.models.subscription import Subscription, SubscriptionStatus
from app.billing.services import billing as billing_service
from app.core.exceptions import ConflictException

logger = logging.getLogger("app.billing.stripe")

STRIPE_STATUS_MAP: dict[str, SubscriptionStatus] = {
    "active": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELED,
    "unpaid": SubscriptionStatus.PAST_DUE,
    # trialing maps contextually in _status_from_stripe
}


async def record_event(db: AsyncSession, event_id: str, event_type: str) -> bool:
    """Insert the event row; return False if this event was seen before.

    The caller must treat ``False`` as "already processed" and skip work.
    The row is committed immediately so a crash mid-processing still marks
    the delivery as seen (Stripe retries get a no-op).
    """
    exists = (
        await db.execute(select(StripeEvent).where(StripeEvent.event_id == event_id))
    ).scalar_one_or_none()
    if exists is not None:
        return False
    db.add(StripeEvent(event_id=event_id, event_type=event_type, processed_at=None))
    try:
        await db.commit()
        return True
    except IntegrityError:
        # Unique-constraint race with a concurrent delivery of the same event.
        await db.rollback()
        return False


async def mark_processed(db: AsyncSession, event_id: str) -> None:
    row = (
        await db.execute(select(StripeEvent).where(StripeEvent.event_id == event_id))
    ).scalar_one_or_none()
    if row is not None:
        row.processed_at = datetime.now(UTC)
        db.add(row)
        await db.commit()


async def get_subscription_by_stripe_id(
    db: AsyncSession, stripe_subscription_id: str
) -> Subscription | None:
    stmt = select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
    return (await db.execute(stmt)).scalar_one_or_none()


def _period_from_stripe(sub_obj: dict[str, object]) -> tuple[datetime, datetime]:
    start = sub_obj.get("current_period_start")
    end = sub_obj.get("current_period_end")
    now = datetime.now(UTC)

    def to_dt(value: object, fallback: datetime) -> datetime:
        if isinstance(value, int | float) and value > 0:
            return datetime.fromtimestamp(float(value), tz=UTC)
        return fallback

    period_start = to_dt(start, now)
    period_end = to_dt(end, period_start + timedelta(days=30))
    return period_start, max(period_end, period_start + timedelta(minutes=1))


def _status_from_stripe(sub_obj: dict[str, object]) -> SubscriptionStatus:
    status = str(sub_obj.get("status", ""))
    if status == "trialing":
        trial_end = sub_obj.get("trial_end")
        trial_active = (
            isinstance(trial_end, int | float)
            and trial_end > 0
            and datetime.fromtimestamp(float(trial_end), tz=UTC) <= datetime.now(UTC)
        )
        if trial_active:
            return SubscriptionStatus.ACTIVE
        return SubscriptionStatus.TRIALING
    mapped = STRIPE_STATUS_MAP.get(status)
    if mapped is None:
        raise ValueError(f"unmapped Stripe subscription status: {status!r}")
    return mapped


async def handle_checkout_completed(db: AsyncSession, session_obj: dict[str, object]) -> str:
    """checkout.session.completed — create/activate the local subscription."""
    metadata = session_obj.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    tenant_raw = metadata.get("tenant_id") or session_obj.get("client_reference_id")
    plan_raw = metadata.get("plan_id")
    stripe_sub_id = session_obj.get("subscription")

    if tenant_raw is None or plan_raw is None or not isinstance(stripe_sub_id, str):
        logger.warning("checkout.session.completed missing expected fields: %s", session_obj)
        return "skipped"

    tenant_id = int(str(tenant_raw))
    plan_row = await crud_plan.get(db, int(str(plan_raw)))
    if plan_row is None:
        logger.warning("checkout for unknown plan_id=%s", plan_raw)
        return "skipped"

    existing_by_tenant = await crud_subscription.get_live_for_tenant(db, tenant_id)
    if existing_by_tenant is not None:
        # Attach the Stripe id if the local live subscription lacks one.
        if existing_by_tenant.stripe_subscription_id is None:
            existing_by_tenant.stripe_subscription_id = stripe_sub_id
            db.add(existing_by_tenant)
            await db.commit()
            await db.refresh(existing_by_tenant)
            return "linked"
        return "duplicate"

    stripe_sub = session_obj.get("stripe_subscription_object")
    if isinstance(stripe_sub, dict):
        status = _status_from_stripe(stripe_sub)
        period_start, period_end = _period_from_stripe(stripe_sub)
        trial_end_dt = None
        trial_end = stripe_sub.get("trial_end")
        if isinstance(trial_end, int | float) and trial_end > 0:
            trial_end_dt = datetime.fromtimestamp(float(trial_end), tz=UTC)
    else:
        status = SubscriptionStatus.ACTIVE
        period_start, period_end = _period_from_stripe({})
        trial_end_dt = None

    sub = Subscription(
        tenant_id=tenant_id,
        plan_id=plan_row.id,
        status=status,
        current_period_start=period_start,
        current_period_end=period_end,
        trial_end=trial_end_dt,
        stripe_subscription_id=stripe_sub_id,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return "created"


async def handle_subscription_sync(db: AsyncSession, stripe_sub: dict[str, object]) -> str:
    """customer.subscription.updated/deleted — sync status into the local row."""
    stripe_id = str(stripe_sub.get("id", ""))
    sub = await get_subscription_by_stripe_id(db, stripe_id)
    if sub is None:
        logger.info("sync for unknown local subscription %s; ignoring", stripe_id)
        return "unknown"

    target_status = _status_from_stripe(stripe_sub)
    if target_status == sub.status:
        return "unchanged"
    if target_status == SubscriptionStatus.CANCELED:
        billing_service.assert_transition(sub.status, SubscriptionStatus.CANCELED)
        sub.canceled_at = datetime.now(UTC)
        sub.cancel_at_period_end = False
        sub.pending_plan_id = None
    elif target_status == SubscriptionStatus.PAST_DUE:
        billing_service.assert_transition(sub.status, SubscriptionStatus.PAST_DUE)
    elif target_status == SubscriptionStatus.ACTIVE:
        billing_service.assert_transition(sub.status, SubscriptionStatus.ACTIVE)
    sub.status = target_status

    period_start, period_end = _period_from_stripe(stripe_sub)
    sub.current_period_start = period_start
    sub.current_period_end = period_end

    db.add(sub)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise ConflictException(detail=f"subscription sync failed: {exc}") from exc
    await db.refresh(sub)
    return "synced"


async def handle_payment_failed(db: AsyncSession, invoice_obj: dict[str, object]) -> str:
    """invoice.payment_failed — drive the subscription into past_due."""
    raw = invoice_obj.get("subscription")
    if not isinstance(raw, str):
        return "skipped"
    sub = await get_subscription_by_stripe_id(db, raw)
    if sub is None or sub.status == SubscriptionStatus.PAST_DUE:
        return "unchanged" if sub is not None else "unknown"
    billing_service.assert_transition(sub.status, SubscriptionStatus.PAST_DUE)
    sub.status = SubscriptionStatus.PAST_DUE
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return "past_due"


async def process_event(db: AsyncSession, event: dict[str, object]) -> str:
    """Dispatch one verified Stripe event. Returns an outcome label.

    Owns the full pipeline: idempotency ledger -> domain handling ->
    processed stamp. Callers must only pass signature-verified payloads.
    """
    event_id = str(event.get("id", ""))
    event_type = str(event.get("type", ""))
    if not event_id or not event_type:
        return "invalid"
    fresh = await record_event(db, event_id, event_type)
    if not fresh:
        return "duplicate"

    data_obj = event.get("data") or {}
    inner = data_obj.get("object", {}) if isinstance(data_obj, dict) else {}

    if event_type == "checkout.session.completed":
        outcome = await handle_checkout_completed(db, inner)
    elif event_type == "customer.subscription.updated":
        outcome = await handle_subscription_sync(db, inner)
    elif event_type == "customer.subscription.deleted":
        deleted = {**inner, "status": "canceled"}
        outcome = await handle_subscription_sync(db, deleted)
    elif event_type == "invoice.payment_failed":
        outcome = await handle_payment_failed(db, inner)
    else:
        outcome = "ignored"

    event_id = str(event.get("id", ""))
    if event_id:
        await mark_processed(db, event_id)
    return outcome
