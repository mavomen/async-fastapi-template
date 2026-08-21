"""Tests for User Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.identity.schemas.user import UserCreate, UserResponse, UserUpdate


class TestUserCreateSchema:
    """Test UserCreate schema validation."""

    def test_valid_user_create(self):
        """Test creating valid UserCreate schema."""
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "password": "SecurePass123!",
        }
        user = UserCreate(**user_data)

        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.full_name == "Test User"
        assert user.password == "SecurePass123!"

    def test_user_create_without_full_name(self):
        """Test UserCreate without optional full_name."""
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "SecurePass123!",
        }
        user = UserCreate(**user_data)

        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.full_name is None

    def test_user_create_invalid_email(self):
        """Test UserCreate with invalid email."""
        user_data = {
            "email": "invalid-email",
            "username": "testuser",
            "password": "SecurePass123!",
        }

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("email",) for error in errors)

    def test_user_create_username_too_short(self):
        """Test UserCreate with username too short."""
        user_data = {
            "email": "test@example.com",
            "username": "ab",
            "password": "SecurePass123!",
        }

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)

    def test_user_create_username_invalid_characters(self):
        """Test UserCreate with invalid username characters."""
        user_data = {
            "email": "test@example.com",
            "username": "test user!",
            "password": "SecurePass123!",
        }

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)

    def test_user_create_password_too_short(self):
        """Test UserCreate with password too short."""
        user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "short",
        }

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("password",) for error in errors)

    def test_user_create_missing_required_fields(self):
        """Test UserCreate with missing required fields."""
        user_data = {
            "email": "test@example.com",
        }

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(**user_data)

        errors = exc_info.value.errors()
        assert len(errors) >= 2  # username and password missing


class TestUserUpdateSchema:
    """Test UserUpdate schema validation."""

    def test_valid_user_update(self):
        """Test creating valid UserUpdate schema."""
        user_data = {
            "email": "updated@example.com",
            "full_name": "Updated Name",
            "is_active": False,
        }
        user = UserUpdate(**user_data)

        assert user.email == "updated@example.com"
        assert user.full_name == "Updated Name"
        assert user.is_active is False

    def test_user_update_all_fields_optional(self):
        """Test UserUpdate with no fields (all optional)."""
        user = UserUpdate()

        assert user.email is None
        assert user.username is None
        assert user.full_name is None
        assert user.password is None
        assert user.is_active is None

    def test_user_update_partial_fields(self):
        """Test UserUpdate with only some fields."""
        user_data = {"full_name": "New Name"}
        user = UserUpdate(**user_data)

        assert user.full_name == "New Name"
        assert user.email is None
        assert user.username is None

    def test_user_update_invalid_email(self):
        """Test UserUpdate with invalid email."""
        user_data = {"email": "not-an-email"}

        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(**user_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("email",) for error in errors)

    def test_user_update_username_too_short(self):
        """Test UserUpdate with username too short."""
        user_data = {"username": "ab"}

        with pytest.raises(ValidationError) as exc_info:
            UserUpdate(**user_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)


class TestUserResponseSchema:
    """Test UserResponse schema."""

    def test_valid_user_response(self):
        """Test creating valid UserResponse schema."""
        from datetime import UTC, datetime

        user_data = {
            "id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "is_active": True,
            "is_verified": False,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        user = UserResponse(**user_data)

        assert user.id == 1
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.is_active is True
        assert user.is_verified is False

    def test_user_response_from_orm(self):
        """Test UserResponse can be created from ORM model."""
        from datetime import UTC, datetime

        from app.identity.models.user import User

        user_model = User(
            id=1,
            email="orm@example.com",
            username="ormuser",
            full_name="ORM User",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )
        user_model.created_at = datetime.now(UTC)
        user_model.updated_at = datetime.now(UTC)

        user_response = UserResponse.model_validate(user_model)

        assert user_response.id == 1
        assert user_response.email == "orm@example.com"
        assert user_response.username == "ormuser"
        assert user_response.is_verified is True

    def test_user_response_excludes_sensitive_fields(self):
        """Test UserResponse doesn't include sensitive fields."""
        from datetime import UTC, datetime

        user_data = {
            "id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "is_active": True,
            "is_verified": False,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
        user = UserResponse(**user_data)

        # Verify sensitive fields are not in the schema
        assert not hasattr(user, "hashed_password")
        assert not hasattr(user, "is_superuser")
