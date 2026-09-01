"""API endpoints for tenant billing invoices.

Invoices are generated from subscription periods (manually or by the
daily sweep task), listed and inspected here. PDF rendering is deferred;
the invoice row plus lines is the document of record.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_event_bus
from app.billing.crud.invoice import invoice as crud_invoice
from app.billing.crud.plan import plan as crud_plan
from app.billing.crud.subscription import subscription as crud_subscription
from app.billing.schemas.invoice import (
    GenerateInvoiceRequest,
    InvoiceListResponse,
    InvoiceResponse,
)
from app.billing.services import invoicing as invoicing_service
from app.core.exceptions import BadRequestException, NotFoundException
from app.events.base import EventBus
from app.identity.auth.permissions import PermissionChecker
from app.identity.models.user import User

router = APIRouter()


@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="List the tenant's invoices",
)
async def list_invoices(
    status: str | None = Query(None, description="Filter by status (draft/open/paid/void)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceListResponse:
    if current_user.tenant_id is None:
        return InvoiceListResponse(items=[])
    items = await crud_invoice.list_for_tenant(
        db,
        current_user.tenant_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return InvoiceListResponse(items=[InvoiceResponse.model_validate(i) for i in items])


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Invoice detail with line items",
)
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceResponse:
    if current_user.tenant_id is None:
        raise NotFoundException(detail="Invoice not found")
    inv = await crud_invoice.get_for_tenant(db, invoice_id, current_user.tenant_id)
    if inv is None:
        raise NotFoundException(detail="Invoice not found")
    return InvoiceResponse.model_validate(inv)


@router.post(
    "/generate",
    response_model=InvoiceResponse,
    status_code=201,
    summary="Generate a draft invoice for the live subscription's period",
    dependencies=[Depends(PermissionChecker(["billing:write"]))],
)
async def generate_invoice(
    obj_in: GenerateInvoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bus: EventBus = Depends(get_event_bus),
) -> InvoiceResponse:
    if current_user.tenant_id is None:
        raise BadRequestException(detail="Invoicing requires a tenant membership")

    sub = await crud_subscription.get_live_for_tenant(db, current_user.tenant_id)
    if sub is None:
        raise NotFoundException(detail="No live subscription to invoice")
    plan_row = await crud_plan.get(db, sub.plan_id)
    if plan_row is None:  # pragma: no cover — FK guarantees existence
        raise NotFoundException(detail="Subscription plan not found")

    inv = await invoicing_service.generate_invoice(
        db,
        sub,
        plan_row,
        period_start=obj_in.period_start,
        period_end=obj_in.period_end,
    )
    await bus.publish(invoicing_service.invoice_event("generated", inv, current_user.id))
    return InvoiceResponse.model_validate(inv)


@router.post(
    "/{invoice_id}/issue",
    response_model=InvoiceResponse,
    summary="Issue a draft invoice (draft -> open)",
    dependencies=[Depends(PermissionChecker(["billing:write"]))],
)
async def issue_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bus: EventBus = Depends(get_event_bus),
) -> InvoiceResponse:
    await _ensure_tenant_invoice(db, invoice_id, current_user)
    inv = await invoicing_service.issue(db, invoice_id, user_id=current_user.id)
    await bus.publish(invoicing_service.invoice_event("issued", inv, current_user.id))
    return InvoiceResponse.model_validate(inv)


@router.post(
    "/{invoice_id}/pay",
    response_model=InvoiceResponse,
    summary="Mark an open invoice paid (open -> paid)",
    dependencies=[Depends(PermissionChecker(["billing:write"]))],
)
async def pay_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bus: EventBus = Depends(get_event_bus),
) -> InvoiceResponse:
    """Manual payment capture until a payment provider drives this state."""
    await _ensure_tenant_invoice(db, invoice_id, current_user)
    inv = await invoicing_service.mark_paid(db, invoice_id)
    await bus.publish(invoicing_service.invoice_event("paid", inv, current_user.id))
    return InvoiceResponse.model_validate(inv)


@router.post(
    "/{invoice_id}/void",
    response_model=InvoiceResponse,
    summary="Void an invoice (releases its period for re-issue)",
    dependencies=[Depends(PermissionChecker(["billing:write"]))],
)
async def void_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bus: EventBus = Depends(get_event_bus),
) -> InvoiceResponse:
    await _ensure_tenant_invoice(db, invoice_id, current_user)
    inv = await invoicing_service.void(db, invoice_id)
    await bus.publish(invoicing_service.invoice_event("voided", inv, current_user.id))
    return InvoiceResponse.model_validate(inv)


async def _ensure_tenant_invoice(db: AsyncSession, invoice_id: int, current_user: User) -> None:
    """404 unless the invoice belongs to the caller's tenant."""
    if current_user.tenant_id is None:
        raise NotFoundException(detail="Invoice not found")
    inv = await crud_invoice.get_for_tenant(db, invoice_id, current_user.tenant_id)
    if inv is None:
        raise NotFoundException(detail="Invoice not found")
