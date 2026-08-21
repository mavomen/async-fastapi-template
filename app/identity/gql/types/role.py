"""Strawberry type for Role model."""

import strawberry


@strawberry.type
class RoleType:
    """Public representation of a role."""

    id: int
    name: str
    description: str | None
    permissions: list[str] = strawberry.field(default_factory=list)
