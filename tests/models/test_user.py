"""Tests for User model."""

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class TestUserModel:
    """Test User model structure and behavior."""

    def test_user_table_name(self):
        """Verify User table name."""
        assert User.__tablename__ == "users"

    def test_user_has_required_columns(self):
        """Verify User has all required columns."""
        mapper = inspect(User)
        column_names = {col.key for col in mapper.columns}

        required_columns = {
            "id",
            "email",
            "username",
            "full_name",
            "hashed_password",
            "is_active",
            "is_superuser",
            "is_verified",
            "email_verified_at",
            "last_login_at",
            "created_at",
            "updated_at",
        }

        assert required_columns.issubset(column_names)

    def test_user_email_is_unique(self):
        """Verify email column has unique constraint."""
        mapper = inspect(User)
        email_col = mapper.columns["email"]
        assert email_col.unique is True

    def test_user_username_is_unique(self):
        """Verify username column has unique constraint."""
        mapper = inspect(User)
        username_col = mapper.columns["username"]
        assert username_col.unique is True

    def test_user_email_is_indexed(self):
        """Verify email column is indexed."""
        mapper = inspect(User)
        email_col = mapper.columns["email"]
        assert email_col.index is True

    def test_user_username_is_indexed(self):
        """Verify username column is indexed."""
        mapper = inspect(User)
        username_col = mapper.columns["username"]
        assert username_col.index is True

    def test_user_repr(self):
        """Verify User __repr__ method."""
        user = User(
            id=1,
            email="test@example.com",
            username="testuser",
            hashed_password="hashed",
        )
        repr_str = repr(user)
        assert "User" in repr_str
        assert "id=1" in repr_str
        assert "email=test@example.com" in repr_str
        assert "username=testuser" in repr_str

    def test_user_default_values(self):
        """Verify User default values are defined in model."""
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password="hashed",
        )

        # Note: SQLAlchemy defaults are applied at database level, not on instantiation
        # We verify the column definitions have defaults
        mapper = inspect(User)
        assert mapper.columns["is_active"].default is not None
        assert mapper.columns["is_superuser"].default is not None
        assert mapper.columns["is_verified"].default is not None
        assert user.full_name is None
        assert user.email_verified_at is None
        assert user.last_login_at is None


@pytest.mark.asyncio
async def test_user_creation_in_db(db_session: AsyncSession):
    """Test creating a user in the database."""
    user = User(
        email="newuser@example.com",
        username="newuser",
        full_name="New User",
        hashed_password="hashedpassword123",
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.email == "newuser@example.com"
    assert user.username == "newuser"
    assert user.full_name == "New User"
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None


@pytest.mark.asyncio
async def test_user_query_by_email(db_session: AsyncSession):
    """Test querying user by email."""
    user = User(
        email="query@example.com",
        username="queryuser",
        hashed_password="hashed",
    )

    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.email == "query@example.com"))
    found_user = result.scalar_one_or_none()

    assert found_user is not None
    assert found_user.email == "query@example.com"
    assert found_user.username == "queryuser"


@pytest.mark.asyncio
async def test_user_query_by_username(db_session: AsyncSession):
    """Test querying user by username."""
    user = User(
        email="username@example.com",
        username="uniqueuser",
        hashed_password="hashed",
    )

    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.username == "uniqueuser"))
    found_user = result.scalar_one_or_none()

    assert found_user is not None
    assert found_user.username == "uniqueuser"


@pytest.mark.asyncio
async def test_user_update(db_session: AsyncSession):
    """Test updating user fields."""
    user = User(
        email="update@example.com",
        username="updateuser",
        hashed_password="hashed",
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    user.full_name = "Updated Name"
    user.is_verified = True
    await db_session.commit()
    await db_session.refresh(user)

    assert user.full_name == "Updated Name"
    assert user.is_verified is True


@pytest.mark.asyncio
async def test_user_delete(db_session: AsyncSession):
    """Test deleting a user."""
    user = User(
        email="delete@example.com",
        username="deleteuser",
        hashed_password="hashed",
    )

    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    await db_session.delete(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.id == user_id))
    found_user = result.scalar_one_or_none()

    assert found_user is None
