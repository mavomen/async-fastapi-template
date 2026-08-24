"""CRUD operations for billing subscriptions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models.subscription import LIVE_STATUSES, Subscription


class CRUDSubscription:
    """Subscription-specific queries."""

    async def get(self, db: AsyncSession, id: int) -> Subscription | None:
        return (
            await db.execute(select(Subscription).where(Subscription.id == id))
        ).scalar_one_or_none()

    async def get_live_for_tenant(
        self, db: AsyncSession, tenant_id: int | None
    ) -> Subscription | None:
        """Return the tenant's live subscription (trialing/active/past_due), if any."""
        # ``is_`` cannot take a bound parameter in Postgres, so split the
        # NULL and non-NULL cases instead of using ``tenant_id.is_(tenant_id)``.
        tenant_cond = (
            Subscription.tenant_id.is_(None)
            if tenant_id is None
            else Subscription.tenant_id == tenant_id
        )
        stmt = (
            select(Subscription)
            .where(
                tenant_cond,
                Subscription.status.in_(LIVE_STATUSES),
            )
            .order_by(Subscription.id.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def create(self, db: AsyncSession, obj: Subscription) -> Subscription:
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj


subscription = CRUDSubscription()
