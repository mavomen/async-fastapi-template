"""Base mixin for tenant‑scoped models."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class TenantBaseModel(BaseModel):
    """Base model with tenant_id for multi‑tenant isolation."""

    __abstract__ = True

    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Relationship back to tenant (optional, for convenience)
    # We can add it later when the Tenant model is imported.
