"""CRUD operations for User model."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for User model."""

    async def get_by_email(self, db: AsyncSession, *, email: str) -> User | None:
        """Get user by email.

        Args:
            db: Database session
            email: User email

        Returns:
            User instance or None if not found
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, *, username: str) -> User | None:
        """Get user by username.

        Args:
            db: Database session
            username: Username

        Returns:
            User instance or None if not found
        """
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        """Create new user with hashed password.

        Args:
            db: Database session
            obj_in: User creation schema

        Returns:
            Created user instance
        """
        # TODO: Hash password before storing (will be implemented in auth module)
        db_obj = User(
            email=obj_in.email,
            username=obj_in.username,
            full_name=obj_in.full_name,
            hashed_password=obj_in.password,  # TODO: Replace with hashed password
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: User,
        obj_in: UserUpdate,
    ) -> User:
        """Update user with optional password hashing.

        Args:
            db: Database session
            db_obj: Existing user instance
            obj_in: User update schema

        Returns:
            Updated user instance
        """
        update_data = obj_in.model_dump(exclude_unset=True)

        # TODO: Hash password if provided (will be implemented in auth module)
        if "password" in update_data:
            hashed_password = update_data.pop("password")
            update_data["hashed_password"] = hashed_password

        return await super().update(db, db_obj=db_obj, obj_in=update_data)

    async def is_active(self, user: User) -> bool:
        """Check if user is active.

        Args:
            user: User instance

        Returns:
            True if user is active
        """
        return user.is_active

    async def is_superuser(self, user: User) -> bool:
        """Check if user is superuser.

        Args:
            user: User instance

        Returns:
            True if user is superuser
        """
        return user.is_superuser


# Create a singleton instance
user = CRUDUser(User)
