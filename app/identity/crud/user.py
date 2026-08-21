"""CRUD operations for User model."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash
from app.crud.base import CRUDBase
from app.identity.models.role import Role
from app.identity.models.user import User
from app.identity.schemas.user import UserCreate, UserUpdate


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

    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        objs_in: list[UserCreate],
    ) -> list[User]:
        """Create multiple users in a single transaction with password hashing."""
        db_objs = []
        for obj_in in objs_in:
            create_data = obj_in.model_dump()
            create_data["hashed_password"] = get_password_hash(create_data.pop("password"))
            db_objs.append(self.model(**create_data))

        db.add_all(db_objs)
        await db.commit()
        for obj in db_objs:
            await db.refresh(obj)
        return db_objs

    async def update(  # type: ignore[override]
        self,
        db: AsyncSession,
        *,
        db_obj: User,
        obj_in: UserUpdate,
    ) -> User:
        """Update user with optional password hashing."""
        update_data = obj_in.model_dump(exclude_unset=True)

        if update_data.get("password"):
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

    async def get_by_oauth(
        self,
        db: AsyncSession,
        *,
        provider: str,
        provider_id: str,
    ) -> User | None:
        """Get user by OAuth provider and provider ID."""
        result = await db.execute(
            select(User).where(
                User.oauth_provider == provider,
                User.oauth_provider_id == provider_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_oauth_user(
        self,
        db: AsyncSession,
        *,
        email: str,
        username: str,
        provider: str,
        provider_id: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> User:
        """Create a new user from OAuth login."""
        import secrets

        from app.core.security import get_password_hash

        db_obj = User(
            email=email,
            username=username,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            is_verified=True,
            email_verified_at=datetime.now(UTC),
            oauth_provider=provider,
            oauth_provider_id=provider_id,
            oauth_access_token=access_token,
            oauth_refresh_token=refresh_token,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def link_oauth_account(
        self,
        db: AsyncSession,
        *,
        user: User,
        provider: str,
        provider_id: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> User:
        """Link an OAuth account to an existing user."""
        user.oauth_provider = provider
        user.oauth_provider_id = provider_id
        if access_token:
            user.oauth_access_token = access_token
        if refresh_token:
            user.oauth_refresh_token = refresh_token
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def is_active(self, user: User) -> bool:
        """Check if user is active."""
        return user.is_active

    async def is_superuser(self, user: User) -> bool:
        """Check if user is superuser."""
        return user.is_superuser


# Singleton instance
user = CRUDUser(User)
