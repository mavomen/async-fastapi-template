"""Pagination utilities for API responses."""

from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Params(BaseModel):
    """Pagination parameters."""

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    size: int = Field(50, ge=1, le=100, description="Page size (max 100)")

    @property
    def skip(self) -> int:
        """Calculate number of records to skip.

        Returns:
            Number of records to skip
        """
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        """Get page size limit.

        Returns:
            Page size
        """
        return self.size


class Page(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T] = Field(description="List of items in current page")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    size: int = Field(description="Page size")
    pages: int = Field(description="Total number of pages")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        params: Params,
    ) -> "Page[T]":
        """Create paginated response.

        Args:
            items: List of items for current page
            total: Total number of items
            params: Pagination parameters

        Returns:
            Paginated response
        """
        pages = ceil(total / params.size) if total > 0 else 0

        return cls(
            items=items,
            total=total,
            page=params.page,
            size=params.size,
            pages=pages,
        )

    model_config = {"arbitrary_types_allowed": True}
