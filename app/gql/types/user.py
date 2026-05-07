"""Strawberry type for User model."""

from datetime import datetime

import strawberry

from app.gql.types.role import RoleType


@strawberry.type
class UserType:
    """Public representation of a user, exposing only safe fields."""

    id: int
    email: str
    username: str
    full_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    roles: list[RoleType] = strawberry.field(default_factory=list)
