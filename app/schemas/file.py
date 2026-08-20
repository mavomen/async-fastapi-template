"""Pydantic schemas for file operations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FileResponse(BaseModel):
    """Schema for file metadata responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    storage_path: str
    checksum_sha256: str
    uploader_id: int | None = None
    thumbnail_path_small: str | None = None
    thumbnail_path_medium: str | None = None
    thumbnail_path_large: str | None = None
    url: str | None = None
    thumbnail_urls: dict[str, str | None] | None = None
    metadata_: dict[str, Any] | None = Field(None, alias="metadata")
    created_at: datetime
    updated_at: datetime


class FileListResponse(BaseModel):
    """Paginated list of files."""

    items: list[FileResponse]
    total: int
    page: int
    per_page: int
