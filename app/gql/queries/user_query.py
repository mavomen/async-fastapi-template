"""User-related GraphQL queries."""

from typing import Any

import strawberry
from strawberry.types import Info

from app.core.database import sessionmanager
from app.crud.user import user as crud_user
from app.gql.types.role import RoleType
from app.gql.types.user import UserType


def _user_to_type(user: Any) -> UserType:
    return UserType(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[
            RoleType(
                id=r.id,
                name=r.name,
                description=r.description,
                permissions=[p.name for p in r.permissions],
            )
            for r in user.roles
        ],
    )


@strawberry.type
class UserQuery:
    """
    Queries for reading user data.
    """

    @strawberry.field(description="Fetch the currently authenticated user.")  # type: ignore[untyped-decorator]
    async def me(self, info: Info) -> UserType:
        """
        Returns the current user from the request context.
        """
        user = info.context["current_user"]
        return _user_to_type(user)

    @strawberry.field(description="Fetch a user by ID. Requires authentication.")  # type: ignore[untyped-decorator]
    async def user(self, info: Info, user_id: int) -> UserType | None:
        """
        Retrieve a specific user. Requires user:read permission.
        """
        from app.auth.permissions import has_permission

        current_user = info.context.get("current_user")
        if not current_user or not has_permission(current_user, ["user:read"]):
            raise PermissionError("Not enough permissions")

        async with sessionmanager.reader_session() as db:
            user = await crud_user.get_with_roles(db, id=user_id)
            if not user:
                return None
            return _user_to_type(user)
