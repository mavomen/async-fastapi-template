"""CRUD operations for TenantIPRule model."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.models.tenant_ip_rule import TenantIPRule


class CRUDTenantIPRule:
    """CRUD for tenant IP access rules."""

    async def get_multi_by_tenant(
        self, db: AsyncSession, *, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> list[TenantIPRule]:
        result = await db.execute(
            select(TenantIPRule)
            .where(TenantIPRule.tenant_id == tenant_id)
            .order_by(TenantIPRule.priority.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, *, id: int) -> TenantIPRule | None:
        result = await db.execute(select(TenantIPRule).where(TenantIPRule.id == id))
        return result.scalar_one_or_none()

    async def create(  # noqa: PLR0913
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        ip_or_cidr: str,
        action: str,
        priority: int = 0,
        description: str | None = None,
    ) -> TenantIPRule:
        rule = TenantIPRule(
            tenant_id=tenant_id,
            ip_or_cidr=ip_or_cidr,
            action=action,
            priority=priority,
            description=description,
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return rule

    async def update(  # noqa: PLR0913
        self,
        db: AsyncSession,
        *,
        db_obj: TenantIPRule,
        ip_or_cidr: str | None = None,
        action: str | None = None,
        priority: int | None = None,
        description: str | None = None,
    ) -> TenantIPRule:
        if ip_or_cidr is not None:
            db_obj.ip_or_cidr = ip_or_cidr
        if action is not None:
            db_obj.action = action
        if priority is not None:
            db_obj.priority = priority
        if description is not None:
            db_obj.description = description
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int) -> TenantIPRule | None:
        obj = await self.get(db, id=id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj


tenant_ip_rule = CRUDTenantIPRule()
