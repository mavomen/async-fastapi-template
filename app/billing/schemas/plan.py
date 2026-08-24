"""Pydantic schemas for billing plans."""

from pydantic import BaseModel, ConfigDict, Field

from app.billing.models.plan import PlanInterval


class PlanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe unique identifier",
    )
    description: str | None = None
    price_cents: int = Field(..., ge=0, le=10_000_000_000)
    currency: str = Field("usd", min_length=3, max_length=3, pattern=r"^[a-z]{3}$")
    interval: PlanInterval
    trial_days: int = Field(0, ge=0, le=365)
    is_active: bool = True


class PlanUpdate(BaseModel):
    """Partial plan update.

    ``currency`` and ``interval`` are intentionally immutable — changing
    them would silently alter terms for existing subscribers. Create a new
    plan and migrate subscriptions instead.
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    price_cents: int | None = Field(None, ge=0, le=10_000_000_000)
    trial_days: int | None = Field(None, ge=0, le=365)
    is_active: bool | None = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    price_cents: int
    currency: str
    interval: PlanInterval
    trial_days: int
    is_active: bool


class PlanListResponse(BaseModel):
    items: list[PlanResponse]
