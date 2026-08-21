"""Tenant IP access control rules."""

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.tenant_base import TenantBaseModel


class TenantIPRule(TenantBaseModel):
    """IP allow/deny rule scoped to a tenant."""

    __tablename__ = "tenant_ip_rules"

    ip_or_cidr: Mapped[str] = mapped_column(String(45), nullable=False)
    action: Mapped[str] = mapped_column(
        SAEnum("allow", "deny", name="ip_rule_action"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<TenantIPRule(id={self.id}, tenant_id={self.tenant_id}, {self.ip_or_cidr}={self.action})>"
