"""Pydantic schemas for usage metering."""

from datetime import datetime

from pydantic import BaseModel, Field


class DimensionUsage(BaseModel):
    """One metered dimension's current-period snapshot."""

    dimension: str
    used: int = Field(..., ge=0, description="Units consumed so far this period")
    included_quantity: int = Field(..., ge=0, description="Free allowance per period")
    unit_amount_cents: int = Field(..., ge=0, description="Overage price per unit")


class UsageResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    dimensions: list[DimensionUsage]
