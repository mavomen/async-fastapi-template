"""Pydantic schemas for Tenant IP rule management."""

from pydantic import BaseModel, Field


class IPRuleCreate(BaseModel):
    """Schema for creating a tenant IP rule."""

    tenant_id: int
    ip_or_cidr: str = Field(..., max_length=45)
    action: str = Field(..., pattern="^(allow|deny)$")
    priority: int = 0
    description: str | None = None


class IPRuleUpdate(BaseModel):
    """Schema for updating a tenant IP rule."""

    ip_or_cidr: str | None = Field(None, max_length=45)
    action: str | None = Field(None, pattern="^(allow|deny)$")
    priority: int | None = None
    description: str | None = None


class IPRuleResponse(BaseModel):
    """Schema for returning a tenant IP rule."""

    id: int
    tenant_id: int
    ip_or_cidr: str
    action: str
    priority: int
    description: str | None
