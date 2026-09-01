"""Invoice lifecycle service.

Generates invoices from subscription periods, snapshots plan pricing
into line items at generation time (plans may be repriced later), and
enforces the invoice state machine:

    draft -> open -> paid, with void reachable from draft/open.

All money is integer minor units; tax rates are basis points.
"""

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.crud.invoice import invoice as crud_invoice
from app.billing.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.billing.models.plan import Plan
from app.billing.models.subscription import Subscription, SubscriptionStatus
from app.billing.services import dunning as dunning_service
from app.billing.services import usage as usage_service
from app.core.exceptions import ConflictException, NotFoundException
from app.events.base import Event, EventBus

ALLOWED_TRANSITIONS: dict[InvoiceStatus, frozenset[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: frozenset({InvoiceStatus.OPEN, InvoiceStatus.VOID}),
    InvoiceStatus.OPEN: frozenset({InvoiceStatus.PAID, InvoiceStatus.VOID}),
    InvoiceStatus.PAID: frozenset(),
    InvoiceStatus.VOID: frozenset(),
}


class IllegalInvoiceTransitionError(Exception):
    """Raised when an invoice status transition is not allowed."""

    def __init__(self, current: InvoiceStatus, target: InvoiceStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Illegal invoice transition: {current} -> {target}")


def assert_invoice_transition(current: InvoiceStatus, target: InvoiceStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise IllegalInvoiceTransitionError(current, target)


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------


def compute_totals(lines: list[InvoiceLine]) -> tuple[int, int]:
    """Return ``(subtotal_cents, tax_cents)`` across lines."""
    subtotal = sum(line.compute_amount() for line in lines)
    tax = sum(line.compute_tax() for line in lines)
    return subtotal, tax


def apply_totals(invoice: Invoice) -> Invoice:
    """Recompute and store subtotal/tax/total from the invoice's lines."""
    invoice.subtotal_cents, invoice.tax_cents = compute_totals(list(invoice.lines))
    invoice.total_cents = invoice.subtotal_cents + invoice.tax_cents
    return invoice


async def append_metered_lines(
    invoice: Invoice,
    plan: Plan,
    tenant_id: int | None,
    period_start: datetime,
) -> None:
    """Add one overage-only line per metered dimension with recorded usage.

    ``billable = max(0, used - included_quantity)``; dimensions with no
    overage are skipped. Counter reads fail open (usage -> 0), matching
    the metering service's availability-first stance.
    """
    if tenant_id is None:
        return
    for dimension, cfg in usage_service.extract_metering(plan.metering).items():
        used = await usage_service.get_usage(tenant_id, dimension, period_start)
        overage_cents = usage_service.compute_overage(
            used, cfg["included_quantity"], cfg["unit_amount_cents"]
        )
        if overage_cents <= 0:
            continue
        billable_units = used - cfg["included_quantity"]
        invoice.lines.append(
            InvoiceLine(
                description=f"{dimension} overage ({billable_units} units @ "
                f"{cfg['unit_amount_cents']} cents)",
                quantity=billable_units,
                unit_amount_cents=cfg["unit_amount_cents"],
                tax_rate_bps=0,
                amount_cents=overage_cents,
            )
        )


# ---------------------------------------------------------------------------
# Generation & lifecycle
# ---------------------------------------------------------------------------


async def generate_invoice(
    db: AsyncSession,
    subscription: Subscription,
    plan: Plan,
    *,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> Invoice:
    """Create a draft invoice for one billing period of a subscription.

    The plan's pricing is snapshotted into a single line. A second
    non-voided invoice for the same period start raises 409.
    """
    if not subscription.is_live():
        raise ConflictException(detail="Cannot invoice a non-live subscription")

    p_start = period_start or subscription.current_period_start
    p_end = period_end or subscription.current_period_end
    if p_end <= p_start:
        raise ValueError("period_end must be after period_start")

    existing = await crud_invoice.find_blocking_for_period(db, subscription.id, p_start)
    if existing is not None:
        raise ConflictException(
            detail=f"Invoice {existing.number or existing.id} already covers this period"
        )

    line = InvoiceLine(
        description=f"{plan.name} — subscription period",
        quantity=1,
        unit_amount_cents=plan.price_cents,
        tax_rate_bps=0,
        amount_cents=plan.price_cents,
    )
    inv = Invoice(
        tenant_id=subscription.tenant_id,
        subscription_id=subscription.id,
        status=InvoiceStatus.DRAFT,
        currency=plan.currency,
        period_start=p_start,
        period_end=p_end,
    )
    inv.lines.append(line)
    await append_metered_lines(inv, plan, subscription.tenant_id, p_start)
    apply_totals(inv)

    try:
        return await crud_invoice.create(db, inv)
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException(detail="An invoice already covers this period") from exc


def invoice_event(event_suffix: str, inv: Invoice, user_id: int | None = None) -> Event:
    """Build a ``billing.invoice.<suffix>`` event carrying minimal payload."""
    return Event(
        event_type=f"billing.invoice.{event_suffix}",
        payload={
            "invoice_id": inv.id,
            "tenant_id": inv.tenant_id,
            "subscription_id": inv.subscription_id,
            "status": str(inv.status),
            "total_cents": inv.total_cents,
            "currency": inv.currency,
            "period_start": inv.period_start.isoformat(),
            "period_end": inv.period_end.isoformat(),
        },
        user_id=user_id,
    )


async def issue(db: AsyncSession, invoice_id: int, user_id: int | None = None) -> Invoice:
    """draft -> open; stamps issued_at."""
    inv = await crud_invoice.get(db, invoice_id)
    if inv is None:
        raise NotFoundException(detail="Invoice not found")
    assert_invoice_transition(inv.status, InvoiceStatus.OPEN)
    inv.status = InvoiceStatus.OPEN
    inv.issued_at = datetime.now(UTC)
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


async def mark_paid(db: AsyncSession, invoice_id: int, bus: EventBus | None = None) -> Invoice:
    """open -> paid; stamps paid_at. Payment capture stays external for now.

    When the underlying subscription was in dunning, a successful payment
    recovers it (past_due -> active, counters reset) and publishes
    ``billing.dunning.recovered``.
    """
    inv = await crud_invoice.get(db, invoice_id)
    if inv is None:
        raise NotFoundException(detail="Invoice not found")
    assert_invoice_transition(inv.status, InvoiceStatus.PAID)
    inv.status = InvoiceStatus.PAID
    inv.paid_at = datetime.now(UTC)
    db.add(inv)

    if inv.subscription_id is not None:
        sub = await db.get(Subscription, inv.subscription_id)
        if (
            sub is not None
            and dunning_service.is_dunning(sub)
            and sub.status == SubscriptionStatus.PAST_DUE
        ):
            await dunning_service.recover_subscription(db, bus, sub)

    await db.commit()
    await db.refresh(inv)
    return inv


async def void(db: AsyncSession, invoice_id: int) -> Invoice:
    """draft/open -> void; releases the period slot for re-issue."""
    inv = await crud_invoice.get(db, invoice_id)
    if inv is None:
        raise NotFoundException(detail="Invoice not found")
    assert_invoice_transition(inv.status, InvoiceStatus.VOID)
    inv.status = InvoiceStatus.VOID
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv
