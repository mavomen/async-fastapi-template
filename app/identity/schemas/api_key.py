"""API key Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] | None = None
    expires_at: datetime | None = None


class ApiKeyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    scopes: list[str] | None = None
    is_active: bool | None = None


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    scopes: list[str] | None
    is_active: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreated(ApiKeyResponse):
    raw_key: str
