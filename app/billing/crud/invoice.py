"""CRUD operations for billing invoices."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models.invoice import BLOCKING_STATUSES, Invoice, InvoiceLine


class CRUDInvoice:
    """Invoice-specific queries."""

    async def get(self, db: AsyncSession, id: int) -> Invoice | None:
        return (await db.execute(select(Invoice).where(Invoice.id == id))).scalar_one_or_none()

    async def get_for_tenant(self, db: AsyncSession, id: int, tenant_id: int) -> Invoice | None:
        stmt = select(Invoice).where(Invoice.id == id, Invoice.tenant_id == tenant_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    async def list_for_tenant(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Invoice]:
        stmt = (
            select(Invoice)
            .where(Invoice.tenant_id == tenant_id)
            .order_by(Invoice.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(Invoice.status == status)
        return list((await db.execute(stmt)).scalars().all())

    async def find_blocking_for_period(
        self,
        db: AsyncSession,
        subscription_id: int,
        period_start: datetime,
    ) -> Invoice | None:
        """Return the non-void invoice covering this period start, if any."""
        stmt = select(Invoice).where(
            Invoice.subscription_id == subscription_id,
            Invoice.period_start == period_start,
            Invoice.status.in_(BLOCKING_STATUSES),
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        invoice: Invoice,
        lines: list[InvoiceLine] | None = None,
    ) -> Invoice:
        for line in lines or []:
            invoice.lines.append(line)
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
        return invoice


invoice = CRUDInvoice()
