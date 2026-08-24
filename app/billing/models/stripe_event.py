"""StripeEvent model: idempotency ledger for inbound webhook events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class StripeEvent(BaseModel):
    """One row per processed Stripe event id.

    The unique ``event_id`` is the idempotency gate: replayed deliveries
    hit the unique constraint and are acknowledged without reprocessing.
    """

    __tablename__ = "stripe_events"

    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<StripeEvent(id={self.id}, event_id={self.event_id}, type={self.event_type})>"
