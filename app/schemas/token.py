"""Pydantic schemas for JWT tokens."""

from pydantic import BaseModel, Field


class Token(BaseModel):
    """Schema for access and refresh tokens."""

    access_token: str = Field(..., description="The JWT access token")
    token_type: str = Field("bearer", description="The type of the token")


class TokenPayload(BaseModel):
    """Schema for the payload of a JWT token."""

    sub: str = Field(..., description="The subject of the token (user ID or email)")
    exp: int = Field(..., description="The expiration time of the token")
