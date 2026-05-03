"""Pydantic schemas for Role and Permission."""

from pydantic import BaseModel, ConfigDict


class PermissionRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    model_config = ConfigDict(from_attributes=True)


class RoleRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    permissions: list[PermissionRead] = []
    model_config = ConfigDict(from_attributes=True)
