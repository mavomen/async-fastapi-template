"""WebAuthn credential model for persistent storage."""

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WebAuthnCredential(BaseModel):
    """Stores a user's WebAuthn passkey."""

    __tablename__ = "webauthn_credentials"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    credential_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<WebAuthnCredential(id={self.id}, user_id={self.user_id})>"
