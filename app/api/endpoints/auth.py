"""
API endpoints for user authentication, login, email verification,
WebAuthn passkeys, and refresh tokens.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_email_service
from app.auth.webauthn import (
    begin_authentication,
    begin_registration,
    complete_authentication,
    complete_registration,
)
from app.core.security import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_verification_token,
    decode_refresh_token,
    decode_verification_token,
    get_jwks,
)
from app.crud.user import user as crud_user
from app.decorators.rate_limit import rate_limit
from app.models.user import User
from app.schemas import Token, UserCreate, UserResponse
from app.services.email import EmailService

router = APIRouter()


@router.get("/.well-known/jwks.json")
async def jwks():
    """Serve JWKS for RS256 key validation."""
    return get_jwks()


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
@rate_limit(times=5, seconds=60)
async def register(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """Register a new user."""
    user = await crud_user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )
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
    description="OAuth2 compatible token login. Returns access and refresh tokens.",
    responses={
        200: {"description": "Access and refresh tokens returned"},
        401: {"description": "Incorrect email or password"},
        422: {"description": "Validation error"},
    },
)
@rate_limit(times=10, seconds=60)
async def login_for_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """OAuth2 compatible token login."""
    user = await authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Issue a new access token (and rotated refresh token) using a valid refresh token.",
    responses={
        200: {"description": "New access and refresh tokens returned"},
        401: {"description": "Invalid or expired refresh token, or inactive user"},
        422: {"description": "Validation error"},
    },
)
async def refresh_access_token(
    refresh_token: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Issue a new access token using a valid refresh token."""
    payload = decode_refresh_token(refresh_token)
    user_id = int(payload["sub"])
    user = await crud_user.get(db, id=user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    new_access = create_access_token(subject=user.id)
    new_refresh = create_refresh_token(subject=user.id)  # rotation
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


# ---------- WebAuthn / Passkey endpoints ----------


@router.post("/webauthn/register/begin")
async def webauthn_register_begin(
    current_user: User = Depends(get_current_user),
):
    """Begin WebAuthn passkey registration."""
    options = await begin_registration(
        user_id=str(current_user.id),
        user_name=current_user.email,
        user_display_name=current_user.full_name or current_user.email,
    )
    return options


@router.post("/webauthn/register/complete")
async def webauthn_register_complete(
    credential: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete WebAuthn passkey registration."""
    result = await complete_registration(
        user_id=str(current_user.id),
        credential=credential,
        db=db,
    )
    return result


@router.post("/webauthn/login/begin")
async def webauthn_login_begin(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Begin WebAuthn passkey authentication (user_id = email)."""
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")
    user = await crud_user.get_by_email(db, email=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    options = await begin_authentication(str(user.id), db=db)
    return options


@router.post("/webauthn/login/complete")
async def webauthn_login_complete(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Complete WebAuthn passkey authentication and return JWT."""
    user_id = payload.get("user_id")
    credential = payload.get("credential", {})
    if not user_id or not credential:
        raise HTTPException(status_code=400, detail="user_id and credential required")
    user = await crud_user.get_by_email(db, email=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    success = await complete_authentication(
        user_id=str(user.id),
        credential=credential,
        db=db,
    )
    if success:
        access_token = create_access_token(subject=user.id)
        return {"access_token": access_token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Authentication failed")


# ---------- Email verification ----------


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
