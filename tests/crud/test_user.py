"""Tests for User CRUD operations."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import user as user_crud
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """Test creating a user."""
    user_in = UserCreate(
        email="create@example.com",
        username="createuser",
        password="password123",
        full_name="Create User",
    )

    created_user = await user_crud.create(db_session, obj_in=user_in)

    assert created_user.id is not None
    assert created_user.email == "create@example.com"
    assert created_user.username == "createuser"
    assert created_user.full_name == "Create User"
    assert created_user.hashed_password != "password123"
    assert created_user.hashed_password.startswith("$2b$")  # bcrypt hash prefix


@pytest.mark.asyncio
async def test_get_user_by_id(db_session: AsyncSession):
    """Test getting a user by ID."""
    user_in = UserCreate(
        email="getbyid@example.com",
        username="getbyiduser",
        password="password123",
    )
    created_user = await user_crud.create(db_session, obj_in=user_in)

    retrieved_user = await user_crud.get(db_session, id=created_user.id)

    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.email == created_user.email


@pytest.mark.asyncio
async def test_get_user_by_email(db_session: AsyncSession):
    """Test getting a user by email."""
    user_in = UserCreate(
        email="getbyemail@example.com",
        username="getbyemailuser",
        password="password123",
    )
    created_user = await user_crud.create(db_session, obj_in=user_in)

    retrieved_user = await user_crud.get_by_email(
        db_session, email="getbyemail@example.com"
    )

    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.email == "getbyemail@example.com"


@pytest.mark.asyncio
async def test_get_user_by_username(db_session: AsyncSession):
    """Test getting a user by username."""
    user_in = UserCreate(
        email="getbyusername@example.com",
        username="getbyusernameuser",
        password="password123",
    )
    created_user = await user_crud.create(db_session, obj_in=user_in)

    retrieved_user = await user_crud.get_by_username(
        db_session, username="getbyusernameuser"
    )

    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.username == "getbyusernameuser"


@pytest.mark.asyncio
async def test_get_user_not_found(db_session: AsyncSession):
    """Test getting a non-existent user returns None."""
    retrieved_user = await user_crud.get(db_session, id=99999)
    assert retrieved_user is None


@pytest.mark.asyncio
async def test_get_user_by_email_not_found(db_session: AsyncSession):
    """Test getting user by non-existent email returns None."""
    retrieved_user = await user_crud.get_by_email(
        db_session, email="nonexistent@example.com"
    )
    assert retrieved_user is None


@pytest.mark.asyncio
async def test_update_user(db_session: AsyncSession):
    """Test updating a user."""
    user_in = UserCreate(
        email="update@example.com",
        username="updateuser",
        password="password123",
    )
    created_user = await user_crud.create(db_session, obj_in=user_in)

    user_update = UserUpdate(full_name="Updated Name", is_active=False)
    updated_user = await user_crud.update(
        db_session, db_obj=created_user, obj_in=user_update
    )

    assert updated_user.id == created_user.id
    assert updated_user.full_name == "Updated Name"
    assert updated_user.is_active is False
    assert updated_user.email == "update@example.com"  # Unchanged


@pytest.mark.asyncio
async def test_update_user_password(db_session: AsyncSession):
    """Test updating user password."""
    user_in = UserCreate(
        email="updatepw@example.com",
        username="updatepwuser",
        password="oldpassword",
    )
    created_user = await user_crud.create(db_session, obj_in=user_in)

    user_update = UserUpdate(password="newpassword")
    updated_user = await user_crud.update(
        db_session, db_obj=created_user, obj_in=user_update
    )

    assert updated_user.hashed_password != "newpassword"
    assert updated_user.hashed_password.startswith("$2b$")


@pytest.mark.asyncio
async def test_update_user_partial(db_session: AsyncSession):
    """Test partial update of user."""
    user_in = UserCreate(
        email="partial@example.com",
        username="partialuser",
        password="password123",
        full_name="Original Name",
    )
    created_user = await user_crud.create(db_session, obj_in=user_in)

    user_update = UserUpdate(full_name="New Name")
    updated_user = await user_crud.update(
        db_session, db_obj=created_user, obj_in=user_update
    )

    assert updated_user.full_name == "New Name"
    assert updated_user.email == "partial@example.com"  # Unchanged
    assert updated_user.username == "partialuser"  # Unchanged


@pytest.mark.asyncio
async def test_delete_user(db_session: AsyncSession):
    """Test deleting a user."""
    user_in = UserCreate(
        email="delete@example.com",
        username="deleteuser",
        password="password123",
    )
    created_user = await user_crud.create(db_session, obj_in=user_in)
    user_id = created_user.id

    deleted_user = await user_crud.delete(db_session, id=user_id)

    assert deleted_user is not None
    assert deleted_user.id == user_id

    # Verify user is deleted
    retrieved_user = await user_crud.get(db_session, id=user_id)
    assert retrieved_user is None


@pytest.mark.asyncio
async def test_delete_user_not_found(db_session: AsyncSession):
    """Test deleting a non-existent user returns None."""
    deleted_user = await user_crud.delete(db_session, id=99999)
    assert deleted_user is None


@pytest.mark.asyncio
async def test_get_multi_users(db_session: AsyncSession):
    """Test getting multiple users with pagination."""
    # Create multiple users
    for i in range(5):
        user_in = UserCreate(
            email=f"multi{i}@example.com",
            username=f"multiuser{i}",
            password="password123",
        )
        await user_crud.create(db_session, obj_in=user_in)

    users = await user_crud.get_multi(db_session, skip=0, limit=3)

    assert len(users) >= 3  # At least 3 users (may have more from other tests)


@pytest.mark.asyncio
async def test_get_multi_users_with_skip(db_session: AsyncSession):
    """Test pagination with skip parameter."""
    # Create users
    created_ids = []
    for i in range(5):
        user_in = UserCreate(
            email=f"skip{i}@example.com",
            username=f"skipuser{i}",
            password="password123",
        )
        user = await user_crud.create(db_session, obj_in=user_in)
        created_ids.append(user.id)

    # Get first page
    first_page = await user_crud.get_multi(db_session, skip=0, limit=2)
    # Get second page
    second_page = await user_crud.get_multi(db_session, skip=2, limit=2)

    # Verify different results
    first_ids = {u.id for u in first_page}
    second_ids = {u.id for u in second_page}
    assert len(first_ids & second_ids) == 0  # No overlap


@pytest.mark.asyncio
async def test_count_users(db_session: AsyncSession):
    """Test counting total users."""
    initial_count = await user_crud.count(db_session)

    # Create new users
    for i in range(3):
        user_in = UserCreate(
            email=f"count{i}@example.com",
            username=f"countuser{i}",
            password="password123",
        )
        await user_crud.create(db_session, obj_in=user_in)

    final_count = await user_crud.count(db_session)

    assert final_count == initial_count + 3


@pytest.mark.asyncio
async def test_is_active(db_session: AsyncSession):
    """Test checking if user is active."""
    user_in = UserCreate(
        email="active@example.com",
        username="activeuser",
        password="password123",
    )
    created_user = await user_crud.create(db_session, obj_in=user_in)

    is_active = await user_crud.is_active(created_user)
    assert is_active is True


@pytest.mark.asyncio
async def test_is_superuser(db_session: AsyncSession):
    """Test checking if user is superuser."""
    user_in = UserCreate(
        email="super@example.com",
        username="superuser",
        password="password123",
    )
    created_user = await user_crud.create(db_session, obj_in=user_in)

    is_superuser = await user_crud.is_superuser(created_user)
    assert is_superuser is False  # Default is False
