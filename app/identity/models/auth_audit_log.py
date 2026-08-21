"""Auth audit log model for tracking authentication events."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

AUTH_EVENT_TYPES = frozenset(
    {
        "login_success",
        "login_failure",
        "account_locked",
        "token_refresh",
        "token_revoke",
        "password_change",
        "mfa_enroll",
        "mfa_disable",
        "magic_link_request",
        "magic_link_login",
    }
)


class AuthAuditLog(Base):
    """Tracks authentication-related events for security auditing."""

    __tablename__ = "auth_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<AuthAuditLog(id={self.id}, event={self.event_type}, user={self.user_id})>"
