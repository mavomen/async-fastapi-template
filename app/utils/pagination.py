"""Pagination utilities for offset-based and cursor-based pagination."""

import base64
import json
from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Params(BaseModel):
    """Offset-based pagination parameters."""

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    size: int = Field(50, ge=1, le=100, description="Page size (max 100)")

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


class Page(BaseModel, Generic[T]):
    """Offset-based paginated response."""

    items: list[T] = Field(description="List of items in current page")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    size: int = Field(description="Page size")
    pages: int = Field(description="Total number of pages")

    @classmethod
    def create(cls, items: list[T], total: int, params: Params) -> "Page[T]":
        pages = ceil(total / params.size) if total > 0 else 0
        return cls(items=items, total=total, page=params.page, size=params.size, pages=pages)

    model_config = {"arbitrary_types_allowed": True}


def encode_cursor(value: int) -> str:
    """Encode an integer cursor value into an opaque base64 string."""
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode()


def decode_cursor(cursor: str) -> int:
    """Decode an opaque cursor string back to an integer."""
    return int(json.loads(base64.urlsafe_b64decode(cursor.encode())))


class CursorParams(BaseModel):
    """Cursor-based pagination parameters."""

    cursor: str | None = Field(None, description="Opaque cursor from the previous page response")
    size: int = Field(50, ge=1, le=100, description="Page size (max 100)")

    @property
    def limit(self) -> int:
        return self.size + 1  # fetch one extra to detect has_more


class CursorPage(BaseModel, Generic[T]):
    """Cursor-based paginated response."""

    items: list[T] = Field(description="List of items in current page")
    next_cursor: str | None = Field(None, description="Cursor for the next page (null if no more)")
    has_more: bool = Field(False, description="Whether more pages are available")
    size: int = Field(description="Number of items in this page")

    @classmethod
    def create(cls, items: list[T], params: CursorParams) -> "CursorPage[T]":
        limit = params.limit  # size + 1
        has_more = len(items) > params.size
        page_items = items[: params.size]
        next_cursor = (
            encode_cursor(getattr(page_items[-1], "id", 0)) if has_more and page_items else None
        )
        return cls(
            items=page_items, next_cursor=next_cursor, has_more=has_more, size=len(page_items)
        )

    model_config = {"arbitrary_types_allowed": True}
