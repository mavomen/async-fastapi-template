"""Webhook and webhook delivery models for outgoing webhooks."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.tenant_base import TenantBaseModel


class Webhook(TenantBaseModel):
    """An outgoing webhook endpoint subscribed to one or more event types."""

    __tablename__ = "webhooks"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(
        String(128), nullable=False, doc="HMAC signing secret (returned only at creation)"
    )
    event_types: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, doc="Subscribed event types; None/empty subscribes to all events"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_delivery_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    deliveries: Mapped[list[WebhookDelivery]] = relationship(
        back_populates="webhook",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Webhook(id={self.id}, name={self.name}, url={self.url})>"


class WebhookDelivery(TenantBaseModel):
    """A single delivery attempt record for a webhook event."""

    __tablename__ = "webhook_deliveries"

    webhook_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, default="pending"
    )  # pending | delivered | failed
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(nullable=True)

    webhook: Mapped[Webhook] = relationship(back_populates="deliveries")

    def __repr__(self) -> str:
        return (
            f"<WebhookDelivery(id={self.id}, webhook_id={self.webhook_id}, "
            f"event_type={self.event_type}, status={self.status})>"
        )
