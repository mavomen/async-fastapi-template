"""CRUD operations for User model."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.crud.base import CRUDBase
from app.models.user import User
from app.models.role import Role, Permission
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for User model."""

    async def get_by_email(self, db: AsyncSession, *, email: str) -> User | None:
        """Get user by email."""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, *, username: str) -> User | None:
        """Get user by username."""
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        """Create new user with hashed password."""
        create_data = obj_in.model_dump()
        create_data["hashed_password"] = get_password_hash(create_data.pop("password"))
        db_obj = self.model(**create_data)

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
        """Update user with optional password hashing."""
        update_data = obj_in.model_dump(exclude_unset=True)

        if "password" in update_data and update_data["password"]:
            hashed_password = get_password_hash(update_data.pop("password"))
            update_data["hashed_password"] = hashed_password

        return await super().update(db, db_obj=db_obj, obj_in=update_data)

    async def get_with_roles(self, db: AsyncSession, id: int) -> User | None:
        """Get user with roles and permissions eagerly loaded."""
        result = await db.execute(
            select(User)
            .options(
                selectinload(User.roles).selectinload(Role.permissions),
            )
            .where(User.id == id)
        )
        return result.scalar_one_or_none()

    async def get_multi_with_roles(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """Get multiple users with roles and permissions eagerly loaded."""
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def is_active(self, user: User) -> bool:
        """Check if user is active."""
        return user.is_active

    async def is_superuser(self, user: User) -> bool:
        """Check if user is superuser."""
        return user.is_superuser


# Singleton instance
user = CRUDUser(User)
