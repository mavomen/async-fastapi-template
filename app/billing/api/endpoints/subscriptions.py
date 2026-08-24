"""API endpoints for tenant subscriptions (self-service billing lifecycle).

Subscription operations act on the caller's own tenant and require only
authentication; the plan catalog write path is gated separately with
``billing:write`` (see plans.py).
"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_event_bus
from app.billing.crud.plan import plan as crud_plan
from app.billing.crud.subscription import subscription as crud_subscription
from app.billing.models.plan import Plan
from app.billing.models.subscription import Subscription, SubscriptionStatus
from app.billing.schemas.subscription import (
    CancelRequest,
    ChangePlanRequest,
    PlanChangePreview,
    SubscribeRequest,
    SubscriptionActionResponse,
    SubscriptionResponse,
)
from app.billing.schemas.usage import DimensionUsage, UsageResponse
from app.billing.services import billing as billing_service
from app.billing.services import usage as usage_service
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.events.base import EventBus
from app.identity.models.user import User

router = APIRouter()


async def _require_live_subscription(db: AsyncSession, tenant_id: int | None) -> Subscription:
    sub = await crud_subscription.get_live_for_tenant(db, tenant_id)
    if sub is None:
        raise NotFoundException(detail="No active subscription found")
    return sub


def _require_tenant(current_user: User) -> int | None:
    if current_user.tenant_id is None and not current_user.is_superuser:
        raise BadRequestException(detail="Billing requires a tenant membership")
    return current_user.tenant_id


async def _require_active_plan(db: AsyncSession, plan_id: int) -> Plan:
    plan_obj = await crud_plan.get(db, plan_id)
    if plan_obj is None or not plan_obj.is_active:
        raise BadRequestException(detail="Plan is not available")
    return plan_obj


def _action_response(
    sub: Subscription,
    preview: billing_service.PlanChangePreview | None = None,
    applied_plan_id: int | None = None,
) -> SubscriptionActionResponse:
    """Map service-layer results to the response schema.

    The service returns a frozen dataclass; the API exposes the Pydantic
    model of the same shape (identical field names).
    """
    preview_schema = (
        PlanChangePreview(
            credit_cents=preview.credit_cents,
            charge_cents=preview.charge_cents,
            net_cents=preview.net_cents,
        )
        if preview is not None
        else None
    )
    return SubscriptionActionResponse(
        subscription=SubscriptionResponse.model_validate(sub),
        preview=preview_schema,
        applied_plan_id=applied_plan_id,
    )


@router.post(
    "",
    response_model=SubscriptionActionResponse,
    status_code=201,
    summary="Subscribe the caller's tenant to a plan",
)
async def subscribe(
    obj_in: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bus: EventBus = Depends(get_event_bus),
) -> SubscriptionActionResponse:
    tenant_id = _require_tenant(current_user)
    plan_obj = await _require_active_plan(db, obj_in.plan_id)

    existing = await crud_subscription.get_live_for_tenant(db, tenant_id)
    if existing is not None:
        raise ConflictException(detail="Tenant already has an active subscription")

    now = billing_service.utcnow()
    trial_end = now + timedelta(days=plan_obj.trial_days) if plan_obj.trial_days > 0 else None
    sub = Subscription(
        tenant_id=tenant_id,
        plan_id=plan_obj.id,
        status=(
            SubscriptionStatus.TRIALING if trial_end is not None else SubscriptionStatus.ACTIVE
        ),
        current_period_start=now,
        current_period_end=billing_service.next_period_end(plan_obj, now),
        trial_end=trial_end,
    )
    sub = await crud_subscription.create(db, sub)

    await bus.publish(
        billing_service.subscription_event(
            "trial_started" if trial_end is not None else "started", sub, current_user.id
        )
    )
    return _action_response(sub)


@router.get(
    "/current",
    response_model=SubscriptionResponse,
    summary="Get the tenant's current subscription",
)
async def get_current_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Subscription:
    return await _require_live_subscription(db, current_user.tenant_id)


@router.post(
    "/change-plan",
    response_model=SubscriptionActionResponse,
    summary="Change the tenant's plan (upgrades immediate, downgrades at period end)",
)
async def change_plan(
    obj_in: ChangePlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bus: EventBus = Depends(get_event_bus),
) -> SubscriptionActionResponse:
    sub = await _require_live_subscription(db, current_user.tenant_id)
    new_plan = await _require_active_plan(db, obj_in.plan_id)
    current_plan = await crud_plan.get(db, sub.plan_id)
    if current_plan is None:
        raise NotFoundException(detail="Current plan no longer exists")
    if new_plan.id == current_plan.id:
        raise BadRequestException(detail="Subscription is already on this plan")

    try:
        decision = billing_service.decide_plan_change(
            current_plan, new_plan, sub, billing_service.utcnow()
        )
    except ValueError as exc:
        raise BadRequestException(detail=str(exc)) from exc

    now = billing_service.utcnow()
    if decision.effective == "immediate" and decision.preview is not None:
        sub.plan_id = new_plan.id
        sub.pending_plan_id = None
        sub.current_period_start = now
        sub.current_period_end = billing_service.next_period_end(new_plan, now)
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        preview = decision.preview
        applied_plan_id = None
    else:
        sub.pending_plan_id = new_plan.id
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        preview = None
        applied_plan_id = new_plan.id

    await bus.publish(billing_service.subscription_event("plan_changed", sub, current_user.id))
    return _action_response(sub, preview=preview, applied_plan_id=applied_plan_id)


@router.post(
    "/cancel",
    response_model=SubscriptionActionResponse,
    summary="Cancel the subscription (at period end unless immediate=True)",
)
async def cancel_subscription(
    obj_in: CancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bus: EventBus = Depends(get_event_bus),
) -> SubscriptionActionResponse:
    sub = await _require_live_subscription(db, current_user.tenant_id)

    if obj_in.immediate:
        try:
            billing_service.assert_transition(sub.status, SubscriptionStatus.CANCELED)
        except billing_service.IllegalTransitionError as exc:
            raise ConflictException(detail=str(exc)) from exc
        sub.status = SubscriptionStatus.CANCELED
        sub.canceled_at = billing_service.utcnow()
        sub.cancel_at_period_end = False
        sub.pending_plan_id = None
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        await bus.publish(billing_service.subscription_event("canceled", sub, current_user.id))
        return _action_response(sub)

    if sub.status == SubscriptionStatus.TRIALING:
        # Trials have nothing to "let run out" into a paid period.
        raise BadRequestException(detail="Trials must be canceled immediately")
    sub.cancel_at_period_end = True
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    await bus.publish(billing_service.subscription_event("cancel_scheduled", sub, current_user.id))
    return _action_response(sub)


@router.post(
    "/resume",
    response_model=SubscriptionActionResponse,
    summary="Undo a scheduled cancellation",
)
async def resume_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bus: EventBus = Depends(get_event_bus),
) -> SubscriptionActionResponse:
    sub = await _require_live_subscription(db, current_user.tenant_id)
    if not sub.cancel_at_period_end:
        raise BadRequestException(detail="Subscription is not scheduled for cancellation")
    sub.cancel_at_period_end = False
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    await bus.publish(billing_service.subscription_event("resumed", sub, current_user.id))
    return _action_response(sub)


@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="Current-period usage vs included quantities",
)
async def get_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UsageResponse:
    """Per-dimension usage snapshot for the live subscription's period."""
    if current_user.tenant_id is None:
        raise BadRequestException(detail="Usage requires a tenant membership")
    sub = await _require_live_subscription(db, current_user.tenant_id)
    plan_row = await crud_plan.get(db, sub.plan_id)
    dimensions = usage_service.extract_metering(plan_row.metering if plan_row else None)

    items: list[DimensionUsage] = []
    for dimension, cfg in dimensions.items():
        used = await usage_service.get_usage(
            current_user.tenant_id, dimension, sub.current_period_start
        )
        items.append(
            DimensionUsage(
                dimension=dimension,
                used=used,
                included_quantity=cfg["included_quantity"],
                unit_amount_cents=cfg["unit_amount_cents"],
            )
        )
    return UsageResponse(
        period_start=sub.current_period_start, period_end=sub.current_period_end, dimensions=items
    )
