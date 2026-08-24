"""Tenant model for multi-tenancy."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Tenant(BaseModel):
    """Represents a tenant / organisation."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, doc="Stripe customer object id (cus_...)"
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name={self.name})>"
