"""User model for authentication and user management."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.identity.models.role import user_roles
from app.models.base import SoftDeleteMixin
from app.models.search import SearchMixin
from app.models.tenant_base import TenantBaseModel

if TYPE_CHECKING:
    from app.identity.models.api_key import ApiKey
    from app.identity.models.role import Role
    from app.models.notification import Notification
    from app.models.notification_preference import NotificationPreference


class User(SoftDeleteMixin, SearchMixin, TenantBaseModel):
    """User model with authentication fields."""

    __tablename__ = "users"

    __table_args__ = (Index("ix_users_oauth_provider_id", "oauth_provider", "oauth_provider_id"),)

    # Basic Information
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Authentication
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Brute-force protection
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)

    # Timestamps for email verification and password reset
    email_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # OAuth2 / Social Login
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_access_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    oauth_refresh_token: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # TOTP / 2FA
    totp_secret: Mapped[str | None] = mapped_column(String(32), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    backup_codes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # RBAC - roles relationship
    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",  # eager load roles when accessing user
    )

    # API keys
    api_keys: Mapped[list[ApiKey]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Notification preferences (one per user)
    notification_preference: Mapped[NotificationPreference | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # In-app notification inbox
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation of User."""
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
