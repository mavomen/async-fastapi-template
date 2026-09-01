"""Subscription lifecycle tests against real Postgres (create_all schema)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.crud.subscription import subscription as crud_subscription
from app.billing.models.plan import Plan, PlanInterval
from app.billing.models.subscription import Subscription, SubscriptionStatus
from app.billing.services.billing import (
    IllegalTransitionError,
    assert_transition,
    next_period_end,
)
from app.identity.models.tenant import Tenant


async def make_tenant_row(db: AsyncSession, name: str = "acme") -> int:
    tenant = Tenant(name=name)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant.id


async def make_plan_row(db: AsyncSession, slug: str = "pro", price_cents: int = 4900) -> Plan:
    plan = Plan(
        name=slug.title(),
        slug=slug,
        description=None,
        price_cents=price_cents,
        currency="usd",
        interval=PlanInterval.MONTHLY,
        trial_days=0,
        is_active=True,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


def make_subscription(plan_id: int, tenant_id: int | None) -> Subscription:
    now = datetime.now(UTC)
    return Subscription(
        tenant_id=tenant_id,
        plan_id=plan_id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=now,
        current_period_end=next_period_end(Plan(interval=PlanInterval.MONTHLY), now),
    )


@pytest.mark.asyncio
async def test_get_live_for_tenant_roundtrip(db_session):
    tenant_id = await make_tenant_row(db_session, "roundtrip")
    plan_row = await make_plan_row(db_session)
    sub = await crud_subscription.create(
        db_session, make_subscription(plan_row.id, tenant_id=tenant_id)
    )

    found = await crud_subscription.get_live_for_tenant(db_session, tenant_id)

    assert found is not None
    assert found.id == sub.id
    assert found.status == SubscriptionStatus.ACTIVE
    assert found.is_live() is True


@pytest.mark.asyncio
async def test_only_one_live_subscription_per_tenant(db_session):
    """The partial unique index must reject a second live row for one tenant."""
    tenant_id = await make_tenant_row(db_session, "dup")
    plan_row = await make_plan_row(db_session)
    await crud_subscription.create(db_session, make_subscription(plan_row.id, tenant_id=tenant_id))

    second = make_subscription(plan_row.id, tenant_id=tenant_id)
    db_session.add(second)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_canceled_subscription_does_not_block_resubscribe(db_session):
    """A canceled (non-live) row does not violate the live-per-tenant index."""
    tenant_id = await make_tenant_row(db_session, "resub")
    plan_row = await make_plan_row(db_session)
    canceled = make_subscription(plan_row.id, tenant_id=tenant_id)
    canceled.status = SubscriptionStatus.CANCELED
    canceled.canceled_at = datetime.now(UTC)
    await crud_subscription.create(db_session, canceled)

    again = await crud_subscription.create(
        db_session, make_subscription(plan_row.id, tenant_id=tenant_id)
    )
    assert again.is_live() is True


@pytest.mark.asyncio
async def test_null_tenant_rows_unconstrained_by_partial_index(db_session):
    plan_row = await make_plan_row(db_session)
    first = make_subscription(plan_row.id, tenant_id=None)
    second = make_subscription(plan_row.id, tenant_id=None)
    db_session.add(first)
    db_session.add(second)
    await db_session.commit()
    assert first.id != second.id


def test_transition_rules_on_real_enums():
    assert_transition(SubscriptionStatus.TRIALING, SubscriptionStatus.PAST_DUE)
    with pytest.raises(IllegalTransitionError):
        assert_transition(SubscriptionStatus.CANCELED, SubscriptionStatus.PAST_DUE)
