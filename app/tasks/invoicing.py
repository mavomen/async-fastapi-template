"""Celery task: daily invoice generation sweep.

Scans live subscriptions whose current period has ended and generates a
draft invoice for the elapsed period. Idempotent: the partial unique
index on ``(subscription_id, period_start)`` skips periods already
invoiced. Period *renewal* (advancing ``current_period_*``) is out of
scope here — it belongs to the dunning/renewal work.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.billing.crud.invoice import invoice as crud_invoice
from app.billing.models.invoice import Invoice, InvoiceStatus
from app.billing.models.plan import Plan
from app.billing.models.subscription import LIVE_STATUSES, Subscription
from app.core.celery_app import celery_app
from app.core.database import sessionmanager

logger = logging.getLogger("app.tasks.invoicing")


@celery_app.task(name="app.tasks.invoicing.generate_due_invoices")  # type: ignore[untyped-decorator]
def generate_due_invoices() -> dict[str, int]:
    """Generate draft invoices for every ended subscription period."""
    return asyncio.get_event_loop().run_until_complete(_generate_due_invoices_async())


async def _generate_due_invoices_async() -> dict[str, int]:
    from app.billing.services import invoicing as invoicing_service

    now = datetime.now(UTC)
    generated = skipped = failed = 0

    async with sessionmanager.writer_session() as db:
        stmt = (
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(
                Subscription.status.in_(LIVE_STATUSES),
                Subscription.current_period_end <= now,
            )
        )
        subs = list((await db.execute(stmt)).scalars().all())

        for sub in subs:
            plan_row = sub.plan or await db.get(Plan, sub.plan_id)
            if plan_row is None:
                logger.warning("subscription %s has no plan; skipping", sub.id)
                failed += 1
                continue
            try:
                existing = await crud_invoice.find_blocking_for_period(
                    db, sub.id, sub.current_period_start
                )
                if existing is not None:
                    skipped += 1
                    continue
                inv: Invoice = await invoicing_service.generate_invoice(db, sub, plan_row)
                # Sweep-issued drafts are issued immediately so downstream
                # (dunning, admin views) sees open invoices, not drafts.
                if inv.status == InvoiceStatus.DRAFT:
                    await invoicing_service.issue(db, inv.id)
                generated += 1
            except Exception:
                logger.exception("invoice generation failed for subscription %s", sub.id)
                failed += 1

    logger.info(
        "invoice sweep complete: %d generated, %d already covered, %d failed",
        generated,
        skipped,
        failed,
    )
    return {"generated": generated, "skipped": skipped, "failed": failed}
