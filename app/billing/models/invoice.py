"""Invoice models: billed documents generated from subscription periods.

An ``Invoice`` snapshots what a tenant owes for one billing period.
Amounts are integer minor units; VAT/tax is captured per line in basis
points. Rendering to PDF is intentionally deferred — the document of
record is the invoice row plus its lines.

Invoice numbers are derived from the immutable primary key
(``INV-{issued year}-{id:06d}``) instead of a database sequence: stable,
unique, gapless-free by design, and needs no extra migration surface.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.tenant_base import TenantBaseModel


class InvoiceStatus(enum.StrEnum):
    """Lifecycle states for an invoice.

    Allowed transitions (enforced by app/billing/services/invoicing.py):

        draft -> open | void
        open  -> paid | void
        paid  -> (terminal)
        void  -> (terminal)
    """

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"


#: Statuses that block regeneration for the same subscription period.
BLOCKING_STATUSES: frozenset[InvoiceStatus] = frozenset(
    {InvoiceStatus.DRAFT, InvoiceStatus.OPEN, InvoiceStatus.PAID}
)


class Invoice(TenantBaseModel):
    """A billing document for one subscription period."""

    __tablename__ = "invoices"

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(
            InvoiceStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=InvoiceStatus.DRAFT,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list[InvoiceLine]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # At most one non-voided invoice per (subscription, period). Voiding
    # releases the slot so corrected re-issues are possible.
    __table_args__ = (
        Index(
            "uq_invoice_per_subscription_period",
            "subscription_id",
            "period_start",
            unique=True,
            postgresql_where=text("status <> 'void'"),
        ),
    )

    @property
    def number(self) -> str:
        """Stable human-readable invoice number derived from the PK."""
        year = self.created_at.year if self.created_at else 0
        return f"INV-{year}-{self.id:06d}"

    def __repr__(self) -> str:
        return (
            f"<Invoice(id={self.id}, tenant_id={self.tenant_id}, "
            f"subscription_id={self.subscription_id}, status={self.status}, "
            f"total_cents={self.total_cents})>"
        )


class InvoiceLine(BaseModel):
    """A single billed line on an invoice (snapshot of plan pricing)."""

    __tablename__ = "invoice_lines"

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Tax rate in basis points (e.g. 2000 == 20.00% VAT).
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")

    def compute_amount(self) -> int:
        return (self.quantity or 0) * (self.unit_amount_cents or 0)

    def compute_tax(self) -> int:
        # ``or 0`` keeps this usable on pre-flush instances where column
        # defaults have not been applied yet.
        rate = self.tax_rate_bps or 0
        return round(self.compute_amount() * rate / 10_000)

    def __repr__(self) -> str:
        return (
            f"<InvoiceLine(id={self.id}, invoice_id={self.invoice_id}, "
            f"description={self.description!r}, amount_cents={self.amount_cents})>"
        )
