"""File model — tracks uploaded file metadata and thumbnail paths."""

from typing import Any

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class File(BaseModel):
    """Represents an uploaded file with metadata and thumbnail references."""

    __tablename__ = "files"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    uploader_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    thumbnail_path_small: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_path_medium: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_path_large: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    uploader = relationship("User", foreign_keys=[uploader_id], lazy="selectin")
