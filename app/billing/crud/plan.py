"""CRUD operations for billing plans."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models.plan import Plan
from app.billing.schemas.plan import PlanCreate, PlanUpdate


class CRUDPlan:
    """Plan-specific CRUD helpers on top of plain queries."""

    async def get(self, db: AsyncSession, id: int) -> Plan | None:
        return (await db.execute(select(Plan).where(Plan.id == id))).scalar_one_or_none()

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Plan | None:
        return (await db.execute(select(Plan).where(Plan.slug == slug))).scalar_one_or_none()

    async def list_active(self, db: AsyncSession) -> list[Plan]:
        result = await db.execute(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_cents)
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, obj_in: PlanCreate) -> Plan:
        plan = Plan(**obj_in.model_dump())
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        return plan

    async def update(self, db: AsyncSession, db_obj: Plan, obj_in: PlanUpdate) -> Plan:
        for field, value in obj_in.model_dump(exclude_unset=True).items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


plan = CRUDPlan()
