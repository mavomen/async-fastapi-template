"""Pydantic schemas for billing subscriptions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.billing.models.subscription import SubscriptionStatus


class SubscribeRequest(BaseModel):
    plan_id: int = Field(..., gt=0)


class ChangePlanRequest(BaseModel):
    plan_id: int = Field(..., gt=0)


class CancelRequest(BaseModel):
    """Cancel the tenant's subscription.

    Default is at period end; ``immediate=True`` cancels right now.
    """

    immediate: bool = False


class PlanChangePreview(BaseModel):
    """Proration details for an immediate plan change."""

    credit_cents: int = Field(..., description="Credit granted for unused time on the old plan")
    charge_cents: int = Field(
        ..., description="Prorated charge for the remainder of the period on the new plan"
    )
    net_cents: int = Field(..., description="charge - credit; may be negative")


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int | None
    plan_id: int
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    trial_end: datetime | None
    cancel_at_period_end: bool
    pending_plan_id: int | None
    canceled_at: datetime | None
    created_at: datetime


class SubscriptionActionResponse(BaseModel):
    """Response for subscribe / change-plan / cancel / resume actions."""

    subscription: SubscriptionResponse
    preview: PlanChangePreview | None = Field(
        None, description="Present only for immediate plan changes"
    )
    applied_plan_id: int | None = Field(
        None, description="For scheduled changes, the plan that will apply at period end"
    )
