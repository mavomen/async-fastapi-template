"""Plan model: a billable catalog entry for subscriptions."""

from __future__ import annotations

import enum

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PlanInterval(enum.StrEnum):
    """Billing cadence for a plan."""

    MONTHLY = "monthly"
    YEARLY = "yearly"


class Plan(BaseModel):
    """A plan in the billing catalog.

    Plans are global (not tenant-scoped): tenants subscribe to them.
    Prices are stored as integer minor units (e.g. cents) to avoid
    floating-point money; ``currency`` is an ISO-4217 alphabetic code.
    """

    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    interval: Mapped[PlanInterval] = mapped_column(String(20), nullable=False)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Plan(id={self.id}, slug={self.slug}, price_cents={self.price_cents}, "
            f"interval={self.interval})>"
        )
