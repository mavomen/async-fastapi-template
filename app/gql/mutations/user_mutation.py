"""User-related GraphQL mutations."""

import strawberry
from strawberry.types import Info

from app.core.database import sessionmanager
from app.crud.user import user as crud_user
from app.gql.types.user import UserType
from app.schemas.user import UserCreate, UserUpdate


@strawberry.type
class UserMutation:
    """
    Mutations for creating and updating users.
    """

    @strawberry.mutation(description="Register a new user.")
    async def create_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None = None,
    ) -> UserType:
        """
        Create a new user account.
        """
        async with sessionmanager.session() as db:
            user_in = UserCreate(
                email=email, username=username, password=password, full_name=full_name
            )
            user = await crud_user.create(db, obj_in=user_in)
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

    @strawberry.mutation(description="Update an existing user.")
    async def update_user(
        self,
        info: Info,
        user_id: int,
        full_name: str | None = None,
        is_active: bool | None = None,
    ) -> UserType | None:
        """
        Update a user's details. Requires user:write permission.
        """
        from app.auth.permissions import has_permission

        current_user = info.context.get("current_user")
        if not current_user or not has_permission(current_user, ["user:write"]):
            raise PermissionError("Not enough permissions")

        async with sessionmanager.session() as db:
            user = await crud_user.get(db, id=user_id)
            if not user:
                return None
            update_data = UserUpdate(full_name=full_name, is_active=is_active)
            updated_user = await crud_user.update(db, db_obj=user, obj_in=update_data)
            return UserType(
                id=updated_user.id,
                email=updated_user.email,
                username=updated_user.username,
                full_name=updated_user.full_name,
                is_active=updated_user.is_active,
                is_verified=updated_user.is_verified,
                created_at=updated_user.created_at,
                updated_at=updated_user.updated_at,
                roles=[],
            )
