"""Pydantic schemas for billing invoices."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.billing.models.invoice import InvoiceStatus


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    quantity: int
    unit_amount_cents: int
    tax_rate_bps: int = Field(..., description="Tax/VAT rate in basis points")
    amount_cents: int


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int | None
    subscription_id: int
    status: InvoiceStatus
    currency: str
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    period_start: datetime
    period_end: datetime
    issued_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    lines: list[InvoiceLineResponse]

    @property
    def number(self) -> str:
        year = self.created_at.year if self.created_at else 0
        return f"INV-{year}-{self.id:06d}"


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]


class GenerateInvoiceRequest(BaseModel):
    """Generate an invoice for the live subscription's current period.

    Explicit dates are optional; they default to the subscription's
    ``current_period_start`` / ``current_period_end``.
    """

    period_start: datetime | None = None
    period_end: datetime | None = None
