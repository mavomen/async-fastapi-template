"""Pydantic schemas for billing plans."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.billing.models.plan import PlanInterval


class DimensionConfig(BaseModel):
    """Billing parameters for one metered dimension.

    ``included_quantity`` is free per billing period; usage beyond it is
    invoiced at ``unit_amount_cents`` per unit (overage-only).
    """

    unit_amount_cents: int = Field(..., ge=0, le=100_000_000)
    included_quantity: int = Field(0, ge=0)


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
    metering: dict[str, DimensionConfig] | None = Field(
        None,
        description=(
            "Metered dimensions for usage-based billing, keyed by dimension name "
            "(e.g. {'api_requests': {'unit_amount_cents': 1, 'included_quantity': 10000}})"
        ),
    )


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
    #: Omitted on PATCH = unchanged; explicit ``null`` = clear metering
    #: (CRUDBase uses ``model_dump(exclude_unset=True)``).
    metering: dict[str, DimensionConfig] | None = None


def _metering_out(value: dict[str, dict[str, int]] | None) -> dict[str, DimensionConfig] | None:
    if value is None:
        return None
    return {name: DimensionConfig.model_validate(cfg) for name, cfg in value.items()}


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
    metering: dict[str, DimensionConfig] | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _coerce_metering(cls, data: object) -> object:
        if isinstance(data, dict):
            raw = data.get("metering")
            if isinstance(raw, dict):
                data["metering"] = _metering_out(raw)
        return data


class PlanListResponse(BaseModel):
    items: list[PlanResponse]
