"""Subscription model: a tenant's enrollment in a billing plan."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.billing.models.plan import Plan, PlanInterval
from app.models.tenant_base import TenantBaseModel


class SubscriptionStatus(enum.StrEnum):
    """Lifecycle states for a subscription.

    Allowed transitions (enforced by app/billing/services/billing.py):

        trialing  -> active | past_due | canceled
        active    -> past_due | canceled
        past_due  -> active | canceled | suspended
        canceled  -> (terminal)
        suspended -> (terminal, system-set after final payment failure)
    """

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    SUSPENDED = "suspended"


#: Statuses that count as "live" — a tenant may hold at most one live subscription.
LIVE_STATUSES: frozenset[SubscriptionStatus] = frozenset(
    {SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE}
)


class Subscription(TenantBaseModel):
    """A tenant's subscription to a plan. At most one live per tenant."""

    __tablename__ = "subscriptions"

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            native_enum=False,
            length=20,
            # Store lowercase values ("trialing"), not member names ("TRIALING"),
            # keeping DB rows consistent with API payloads and the partial
            # live-per-tenant index predicate.
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=SubscriptionStatus.TRIALING,
        index=True,
    )
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pending_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, doc="Stripe subscription object id (sub_...)"
    )

    # Dunning state (app/billing/services/dunning.py)
    failed_payment_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_payment_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped[Plan] = relationship(foreign_keys=[plan_id])
    pending_plan: Mapped[Plan | None] = relationship(foreign_keys=[pending_plan_id])

    __table_args__ = (
        Index(
            "uq_live_subscription_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("status IN ('trialing', 'active', 'past_due')"),
        ),
    )

    def is_live(self) -> bool:
        return self.status in LIVE_STATUSES

    def __repr__(self) -> str:
        return (
            f"<Subscription(id={self.id}, tenant_id={self.tenant_id}, "
            f"plan_id={self.plan_id}, status={self.status})>"
        )


# Re-export for convenience so callers can do `from ...subscription import PlanInterval`
__all__ = [
    "LIVE_STATUSES",
    "Plan",
    "PlanInterval",
    "Subscription",
    "SubscriptionStatus",
]
