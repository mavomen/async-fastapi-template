"""User-related GraphQL queries."""

import strawberry
from strawberry.types import Info

from app.core.database import sessionmanager
from app.crud.user import user as crud_user
from app.gql.types.user import UserType


@strawberry.type
class UserQuery:
    """
    Queries for reading user data.
    """

    @strawberry.field(description="Fetch the currently authenticated user.")
    async def me(self, info: Info) -> UserType:
        """
        Returns the current user from the request context.
        """
        user = info.context["current_user"]
        # Convert SQLAlchemy model to Strawberry type
        return UserType(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[],  # or map roles if needed
        )

    @strawberry.field(description="Fetch a user by ID. Requires authentication.")
    async def user(self, info: Info, user_id: int) -> UserType | None:
        """
        Retrieve a specific user. Requires user:read permission.
        """
        from app.auth.permissions import has_permission

        current_user = info.context.get("current_user")
        if not current_user or not has_permission(current_user, ["user:read"]):
            raise PermissionError("Not enough permissions")

        async with sessionmanager.session() as db:
            user = await crud_user.get(db, id=user_id)
            if not user:
                return None
            return UserType(
                id=user.id,
                email=user.email,
                username=user.username,
                full_name=user.full_name,
                is_active=user.is_active,
                is_verified=user.is_verified,
                created_at=user.created_at,
                updated_at=user.updated_at,
                roles=[],
            )
