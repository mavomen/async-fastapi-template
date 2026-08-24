"""Stripe integration endpoints.

``POST /billing/stripe/webhook``
    Public intake for Stripe webhook deliveries. Verifies the
    ``Stripe-Signature`` header against ``STRIPE_WEBHOOK_SECRET``, then
    processes the event idempotently (unique event-id ledger). Verified
    payloads are always acknowledged with 2xx so Stripe stops retrying;
    processing errors are logged instead of surfaced as retry noise.

``POST /billing/stripe/checkout-session``
    Authenticated. Creates a hosted checkout session for the caller's
    tenant and returns the URL to redirect to.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_event_bus
from app.billing.crud.plan import plan as crud_plan
from app.billing.crud.subscription import subscription as crud_subscription
from app.billing.services import billing as billing_service
from app.billing.services import stripe_events
from app.billing.services.stripe_client import (
    create_checkout_session,
    create_customer,
    stripe_configured,
)
from app.core.config import settings
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.core.signing import verify_signature_header
from app.events.base import EventBus
from app.identity.models.tenant import Tenant
from app.identity.models.user import User

logger = logging.getLogger("app.billing.stripe")

router = APIRouter()

WEBHOOK_TOLERANCE_SECONDS = 300


class CheckoutSessionRequest(BaseModel):
    plan_id: int = Field(..., gt=0)
    success_url: HttpUrl
    cancel_url: HttpUrl


@router.post(
    "/webhook",
    summary="Stripe webhook intake (signature-verified, idempotent)",
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    bus: EventBus = Depends(get_event_bus),
) -> Response:
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Billing provider not configured")

    body = await request.body()
    signature = request.headers.get("stripe-signature")
    if not verify_signature_header(
        body,
        settings.STRIPE_WEBHOOK_SECRET,
        signature,
        tolerance_seconds=WEBHOOK_TOLERANCE_SECONDS,
    ):
        return ORJSONResponse(status_code=400, content={"detail": "Invalid signature"})

    try:
        event: dict[str, Any] = await request.json()
    except ValueError:
        return ORJSONResponse(status_code=400, content={"detail": "Invalid JSON"})

    event_id = str(event.get("id", ""))
    event_type = str(event.get("type", ""))
    if not event_id or not event_type:
        return ORJSONResponse(status_code=400, content={"detail": "Missing id/type"})

    try:
        outcome = await stripe_events.process_event(db, event, bus)
    except billing_service.IllegalTransitionError as exc:
        # Verified but inapplicable (e.g. out-of-order delivery): log + ack.
        logger.warning("stripe event %s rejected by state machine: %s", event_id, exc)
        outcome = "rejected"
    except Exception:
        logger.exception("failed processing stripe event %s (%s)", event_id, event_type)
        outcome = "error"

    return ORJSONResponse(content={"received": True, "outcome": outcome})


@router.post(
    "/checkout-session",
    summary="Create a Stripe checkout session for a plan",
)
async def create_checkout(
    obj_in: CheckoutSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    if current_user.tenant_id is None:
        raise BadRequestException(detail="Checkout requires a tenant membership")
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Billing provider not configured")

    plan_row = await crud_plan.get(db, obj_in.plan_id)
    if plan_row is None or not plan_row.is_active:
        raise NotFoundException(detail="Plan is not available")

    live = await crud_subscription.get_live_for_tenant(db, current_user.tenant_id)
    if live is not None:
        raise ConflictException(detail="Tenant already has an active subscription")

    tenant_row: Tenant | None = (
        await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    ).scalar_one_or_none()
    if tenant_row is None:
        raise BadRequestException(detail="Tenant record not found")

    customer_id = tenant_row.stripe_customer_id
    if not customer_id:
        customer = await create_customer(tenant_row.name)
        customer_id = str(customer["id"])
        tenant_row.stripe_customer_id = customer_id
        db.add(tenant_row)
        await db.commit()
        await db.refresh(tenant_row)

    session_obj = await create_checkout_session(
        customer_id=customer_id,
        plan=plan_row,
        success_url=str(obj_in.success_url),
        cancel_url=str(obj_in.cancel_url),
        tenant_id=current_user.tenant_id,
    )
    url = session_obj.get("url")
    if not isinstance(url, str):
        raise BadRequestException(detail="Stripe did not return a checkout URL")
    return {"url": url, "session_id": str(session_obj.get("id", ""))}
