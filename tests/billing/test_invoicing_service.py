"""Invoice service tests: pure math units + real-Postgres lifecycle."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.crud.invoice import invoice as crud_invoice
from app.billing.models.invoice import InvoiceLine, InvoiceStatus
from app.billing.services.invoicing import (
    IllegalInvoiceTransitionError,
    assert_invoice_transition,
    compute_totals,
    generate_invoice,
    issue,
    mark_paid,
    void,
)
from tests.billing.test_subscription_lifecycle import (
    make_plan_row,
    make_subscription,
    make_tenant_row,
)

NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Pure math / state machine
# ---------------------------------------------------------------------------


class TestTotals:
    def test_subtotal_and_tax(self):
        lines = [
            InvoiceLine(description="a", quantity=2, unit_amount_cents=1000, amount_cents=2000),
            InvoiceLine(
                description="b",
                quantity=1,
                unit_amount_cents=500,
                tax_rate_bps=2000,  # 20% VAT
                amount_cents=500,
            ),
        ]
        subtotal, tax = compute_totals(lines)
        assert subtotal == 2500
        assert tax == 100  # 20% of 500

    def test_zero_tax_default(self):
        line = InvoiceLine(description="a", quantity=1, unit_amount_cents=999, amount_cents=999)
        assert compute_totals([line]) == (999, 0)


class TestTransitions:
    @pytest.mark.parametrize(
        ("current", "target"),
        [
            (InvoiceStatus.DRAFT, InvoiceStatus.OPEN),
            (InvoiceStatus.DRAFT, InvoiceStatus.VOID),
            (InvoiceStatus.OPEN, InvoiceStatus.PAID),
            (InvoiceStatus.OPEN, InvoiceStatus.VOID),
        ],
    )
    def test_legal(self, current, target):
        assert_invoice_transition(current, target)

    @pytest.mark.parametrize(
        ("current", "target"),
        [
            (InvoiceStatus.DRAFT, InvoiceStatus.PAID),  # must be issued first
            (InvoiceStatus.OPEN, InvoiceStatus.OPEN),
            (InvoiceStatus.PAID, InvoiceStatus.VOID),
            (InvoiceStatus.VOID, InvoiceStatus.OPEN),
        ],
    )
    def test_illegal(self, current, target):
        with pytest.raises(IllegalInvoiceTransitionError):
            assert_invoice_transition(current, target)


# ---------------------------------------------------------------------------
# Real-Postgres lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_number_is_pk_derived(db_session):
    tenant_id = await make_tenant_row(db_session, "numbered")
    plan_row = await make_plan_row(db_session)
    sub = await db_session_merge(db_session, make_subscription(plan_row.id, tenant_id))
    inv = await generate_invoice(db_session, sub, plan_row)
    await db_session.refresh(inv)
    assert inv.number.startswith("INV-")
    assert inv.number.endswith(f"-{inv.id:06d}")


async def db_session_merge(db: AsyncSession, obj):
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


@pytest.mark.asyncio
async def test_full_lifecycle_generate_issue_pay(db_session):
    tenant_id = await make_tenant_row(db_session, "lifecycle")
    plan_row = await make_plan_row(db_session)
    sub = await db_session_merge(db_session, make_subscription(plan_row.id, tenant_id))

    inv = await generate_invoice(db_session, sub, plan_row)
    assert inv.status is InvoiceStatus.DRAFT
    assert inv.subtotal_cents == plan_row.price_cents
    assert inv.tax_cents == 0
    assert inv.total_cents == plan_row.price_cents
    assert [ln.description for ln in inv.lines] == ["Pro — subscription period"]

    issued = await issue(db_session, inv.id)
    assert issued.status is InvoiceStatus.OPEN
    assert issued.issued_at is not None

    paid = await mark_paid(db_session, issued.id)
    assert paid.status is InvoiceStatus.PAID
    assert paid.paid_at is not None


@pytest.mark.asyncio
async def test_double_generation_conflicts(db_session):
    tenant_id = await make_tenant_row(db_session, "dupe")
    plan_row = await make_plan_row(db_session)
    sub = await db_session_merge(db_session, make_subscription(plan_row.id, tenant_id))

    await generate_invoice(db_session, sub, plan_row)
    from app.core.exceptions import ConflictException

    with pytest.raises(ConflictException):
        await generate_invoice(db_session, sub, plan_row)


@pytest.mark.asyncio
async def test_void_releases_period_for_reissue(db_session):
    tenant_id = await make_tenant_row(db_session, "voided")
    plan_row = await make_plan_row(db_session)
    sub = await db_session_merge(db_session, make_subscription(plan_row.id, tenant_id))

    first = await generate_invoice(db_session, sub, plan_row)
    await void(db_session, first.id)

    second = await generate_invoice(db_session, sub, plan_row)
    assert second.id != first.id
    assert second.status is InvoiceStatus.DRAFT


@pytest.mark.asyncio
async def test_non_live_subscription_rejected(db_session):
    from app.billing.models.subscription import SubscriptionStatus
    from app.core.exceptions import ConflictException

    tenant_id = await make_tenant_row(db_session, "dead")
    plan_row = await make_plan_row(db_session)
    sub = make_subscription(plan_row.id, tenant_id)
    sub.status = SubscriptionStatus.CANCELED
    sub.canceled_at = NOW - timedelta(minutes=1)
    sub = await db_session_merge(db_session, sub)

    with pytest.raises(ConflictException):
        await generate_invoice(db_session, sub, plan_row)


@pytest.mark.asyncio
async def test_explicit_period_overrides_defaults(db_session):
    tenant_id = await make_tenant_row(db_session, "explicit")
    plan_row = await make_plan_row(db_session)
    sub = await db_session_merge(db_session, make_subscription(plan_row.id, tenant_id))

    p_start = NOW - timedelta(days=60)
    p_end = p_start + timedelta(days=30)
    inv = await generate_invoice(db_session, sub, plan_row, period_start=p_start, period_end=p_end)
    assert inv.period_start == p_start
    assert inv.period_end == p_end


@pytest.mark.asyncio
async def test_find_blocking_ignores_voided(db_session):
    tenant_id = await make_tenant_row(db_session, "blocking")
    plan_row = await make_plan_row(db_session)
    sub = await db_session_merge(db_session, make_subscription(plan_row.id, tenant_id))

    inv = await generate_invoice(db_session, sub, plan_row)
    found = await crud_invoice.find_blocking_for_period(db_session, sub.id, inv.period_start)
    assert found is not None and found.id == inv.id

    await void(db_session, inv.id)
    assert await crud_invoice.find_blocking_for_period(db_session, sub.id, inv.period_start) is None


@pytest.mark.asyncio
async def test_list_for_tenant_filters_status(db_session):
    tenant_a = await make_tenant_row(db_session, "lista")
    tenant_b = await make_tenant_row(db_session, "listb")
    plan_row = await make_plan_row(db_session)
    sub_a = await db_session_merge(db_session, make_subscription(plan_row.id, tenant_a))
    sub_b = await db_session_merge(db_session, make_subscription(plan_row.id, tenant_b))

    inv_a = await generate_invoice(db_session, sub_a, plan_row)
    await generate_invoice(db_session, sub_b, plan_row)

    all_a = await crud_invoice.list_for_tenant(db_session, tenant_a)
    assert len(all_a) == 1 and all_a[0].id == inv_a.id

    open_only = await crud_invoice.list_for_tenant(db_session, tenant_b, status="open")
    assert open_only == []
