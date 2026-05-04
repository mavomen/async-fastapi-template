"""
API endpoints for user authentication, login, and email verification.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_email_service
from app.core.security import (
    authenticate_user,
    create_access_token,
    create_verification_token,
    decode_verification_token,
)
from app.crud.user import user as crud_user
from app.models.user import User
from app.schemas import Token, UserCreate, UserResponse
from app.services.email import EmailService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email, username, and password. "
    "Returns the created user's public information.",
    responses={
        201: {"description": "User successfully created"},
        400: {"description": "Email or username already exists"},
        422: {"description": "Validation error"},
    },
)
async def register(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """Register a new user."""
    # Check for existing user by email
    user = await crud_user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )
    # Check for existing user by username
    user = await crud_user.get_by_username(db, username=user_in.username)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username already exists.",
        )
    return await crud_user.create(db, obj_in=user_in)


@router.post(
    "/login",
    response_model=Token,
    summary="Login for access token",
    description="OAuth2 compatible token login. Provide username (email) and password "
    "to receive a JWT access token for future authenticated requests.",
    responses={
        200: {"description": "Access token returned"},
        401: {"description": "Incorrect email or password"},
        422: {"description": "Validation error"},
    },
)
async def login_for_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """OAuth2 compatible token login, get an access token for future requests."""
    user = await authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post(
    "/verify-request",
    status_code=status.HTTP_200_OK,
    summary="Request email verification",
    description="Send a verification email to the current user's email address. "
    "Requires authentication.",
    responses={
        200: {"description": "Verification email sent"},
        400: {"description": "Email already verified"},
        401: {"description": "Not authenticated"},
    },
)
async def request_email_verification(
    current_user: User = Depends(get_current_user),
    email_svc: EmailService = Depends(get_email_service),
) -> Any:
    """Request a verification email be sent to the current user's email."""
    if current_user.is_verified:
        raise HTTPException(400, detail="Email already verified")

    token = create_verification_token(current_user.id)
    await email_svc.send_verification_email(current_user.email, token)
    return {"detail": "Verification email sent"}


@router.get(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description="Verify a user's email address using a token sent via email.",
    responses={
        200: {"description": "Email verified successfully"},
        400: {"description": "Invalid or expired token, or already verified"},
        404: {"description": "User not found"},
    },
)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Verify user email using the token from the verification email."""
    payload = decode_verification_token(token)
    user_id = int(payload["sub"])
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(404, detail="User not found")
    if user.is_verified:
        raise HTTPException(400, detail="Email already verified")

    user.is_verified = True
    user.email_verified_at = datetime.now(UTC)
    db.add(user)
    await db.commit()
    return {"detail": "Email verified successfully"}
