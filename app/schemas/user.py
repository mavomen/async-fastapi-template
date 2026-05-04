"""User Pydantic schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.role import RoleRead


class UserBase(BaseModel):
    """Base User schema with common fields."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    full_name: str | None = Field(None, max_length=100)


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(..., min_length=8, max_length=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "username": "johndoe",
                "full_name": "John Doe",
                "password": "SecurePassword123!",
            }
        }
    )


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    email: EmailStr | None = None
    username: str | None = Field(None, min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    full_name: str | None = Field(None, max_length=100)
    password: str | None = Field(None, min_length=8, max_length=100)
    is_active: bool | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "John Updated Doe",
                "is_active": True,
            }
        }
    )


class UserResponse(UserBase):
    """Schema for user response (public data)."""

    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "email": "user@example.com",
                "username": "johndoe",
                "full_name": "John Doe",
                "is_active": True,
                "is_verified": False,
                "created_at": "2025-05-02T04:30:00Z",
                "updated_at": "2025-05-02T04:30:00Z",
            }
        },
    )


class UserInDB(UserResponse):
    """Schema for user in database (includes sensitive fields)."""

    hashed_password: str
    is_superuser: bool
    email_verified_at: datetime | None
    last_login_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class UserDetailResponse(UserResponse):
    """Detailed user response including roles."""

    roles: list[RoleRead] = []
    is_superuser: bool = False

    model_config = ConfigDict(from_attributes=True)
