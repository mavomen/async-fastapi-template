"""Pydantic schemas for Tenant management."""

from pydantic import BaseModel


class TenantCreate(BaseModel):
    """Schema for creating a new tenant."""

    name: str
    slug: str | None = None
