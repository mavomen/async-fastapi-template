"""
API endpoints for user authentication, login, email verification,
WebAuthn passkeys, and refresh tokens.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_email_service, oauth2_scheme
from app.auth.totp import (
    create_totp_challenge_token,
    decode_totp_challenge_token,
    remove_used_backup_code,
    verify_backup_code,
    verify_totp_code,
)
from app.auth.webauthn import (
    begin_authentication,
    begin_registration,
    complete_authentication,
    complete_registration,
)
from app.core.exceptions import LockedOutException
from app.core.jwt_blacklist import (
    SessionCreatePayload,
    get_session,
    list_active_sessions,
    revoke_all_user_sessions,
    revoke_session,
    store_session,
)
from app.core.security import (
    authenticate_user,
    create_access_token,
    create_magic_link_token,
    create_refresh_token,
    create_verification_token,
    decode_access_token,
    decode_magic_link_token,
    decode_refresh_token,
    decode_verification_token,
    get_jwks,
)
from app.crud.user import user as crud_user
from app.decorators.rate_limit import rate_limit
from app.models.user import User
from app.schemas import Token, UserCreate, UserResponse
from app.schemas.totp import TOTPLoginVerifyRequest
from app.services.auth_audit import log_auth_event
from app.services.email import EmailService

router = APIRouter()


@router.get("/.well-known/jwks.json")
async def jwks() -> Any:
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
@rate_limit(times=5, seconds=60)  # type: ignore[untyped-decorator]
async def register(
    request: Request,
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
    summary="Login for access token",
    description="OAuth2 compatible token login. Returns access and refresh tokens, "
    "or a challenge token if TOTP 2FA is enabled.",
    responses={
        200: {"description": "Access and refresh tokens returned"},
        202: {"description": "TOTP challenge required — provide challenge_token to /login/totp-verify"},
        401: {"description": "Incorrect email or password"},
        423: {"description": "Account locked"},
        422: {"description": "Validation error"},
    },
)
@rate_limit(times=10, seconds=60)  # type: ignore[untyped-decorator]
async def login_for_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """OAuth2 compatible token login."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        user = await authenticate_user(
            db,
            email=form_data.username,
            password=form_data.password,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except LockedOutException as e:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=e.detail,
        )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # If TOTP is enabled, issue a challenge token instead of access tokens
    if user.totp_enabled:
        challenge_token = create_totp_challenge_token(user.id)
        return {
            "totp_required": True,
            "challenge_token": challenge_token,
            "token_type": "totp_challenge",
        }

    return await _issue_tokens(user, db, ip_address, user_agent)


async def _issue_tokens(
    user: User,
    db: AsyncSession,
    ip_address: str | None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Create and store access + refresh tokens for a user."""
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    access_payload = decode_access_token(access_token)
    refresh_payload = decode_refresh_token(refresh_token)
    await store_session(
        user.id,
        SessionCreatePayload(
            jti=access_payload["jti"],
            token_type="access",
            ip=ip_address,
            user_agent=user_agent,
            iat=access_payload["iat"],
            exp=access_payload["exp"],
        ),
    )
    await store_session(
        user.id,
        SessionCreatePayload(
            jti=refresh_payload["jti"],
            token_type="refresh",
            ip=ip_address,
            user_agent=user_agent,
            iat=refresh_payload["iat"],
            exp=refresh_payload["exp"],
        ),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post(
    "/login/totp-verify",
    response_model=Token,
    summary="Complete login with TOTP code",
    description="Exchange a challenge token and a TOTP code (or backup code) "
    "for access and refresh tokens.",
    responses={
        200: {"description": "Access and refresh tokens returned"},
        400: {"description": "Invalid or expired challenge token or TOTP code"},
    },
)
@rate_limit(times=10, seconds=60)  # type: ignore[untyped-decorator]
async def login_with_totp(
    request: Request,
    body: TOTPLoginVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Complete 2FA login by verifying a TOTP code."""
    payload = decode_totp_challenge_token(body.challenge_token)
    user_id = int(payload["sub"])
    user = await crud_user.get(db, id=user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found or inactive",
        )
    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is not enabled for this user",
        )

    valid = verify_totp_code(user.totp_secret, body.code)
    if not valid:
        used_hash = verify_backup_code(body.code, user.backup_codes)
        if used_hash:
            remaining = remove_used_backup_code(used_hash, user.backup_codes)
            user.backup_codes = remaining
            db.add(user)
            await db.commit()
            valid = True

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP or backup code",
        )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await _issue_tokens(user, db, ip_address, user_agent)


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
    request: Request,
    refresh_token: str = Form(...),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Issue a new access token using a valid refresh token."""
    from app.services.auth_audit import log_auth_event

    payload = decode_refresh_token(refresh_token)
    user_id = int(payload["sub"])
    user = await crud_user.get(db, id=user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    new_access = create_access_token(subject=user.id)
    new_refresh = create_refresh_token(subject=user.id)  # rotation

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    old_jti = payload.get("jti")
    old_exp = payload.get("exp", 0)
    if old_jti:
        await revoke_session(user.id, old_jti, old_exp)

    access_payload = decode_access_token(new_access)
    refresh_payload = decode_refresh_token(new_refresh)
    await store_session(
        user.id,
        SessionCreatePayload(
            jti=access_payload["jti"],
            token_type="access",
            ip=ip_address,
            user_agent=user_agent,
            iat=access_payload["iat"],
            exp=access_payload["exp"],
        ),
    )
    await store_session(
        user.id,
        SessionCreatePayload(
            jti=refresh_payload["jti"],
            token_type="refresh",
            ip=ip_address,
            user_agent=user_agent,
            iat=refresh_payload["iat"],
            exp=refresh_payload["exp"],
        ),
    )

    await log_auth_event(
        db,
        event_type="token_refresh",
        user_id=user.id,
        tenant_id=user.tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


# ---------- Passwordless magic link ----------


@router.post(
    "/magic-link/request",
    status_code=status.HTTP_200_OK,
    summary="Request a magic sign-in link",
    description="Send a short-lived magic link to the given email address. "
    "If the email does not exist and MAGIC_LINK_ALLOW_REGISTRATION is enabled, "
    "an account will be created on first use.",
    responses={
        200: {"description": "Magic link sent"},
        429: {"description": "Too many requests"},
    },
)
@rate_limit(times=3, seconds=300)  # type: ignore[untyped-decorator]
async def request_magic_link(
    request: Request,
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    email_svc: EmailService = Depends(get_email_service),
) -> Any:
    """Request a magic sign-in link."""
    token = create_magic_link_token(email)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    await log_auth_event(
        db,
        event_type="magic_link_request",
        ip_address=ip_address,
        user_agent=user_agent,
        details={"email": email},
    )

    await email_svc.send_magic_link_email(to_email=email, token=token)
    return {"detail": "Magic link sent"}


@router.post(
    "/magic-link/verify",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Verify a magic link and receive JWT tokens",
    description="Exchange a magic link token for access and refresh tokens. "
    "If the email is not yet verified, it will be verified automatically.",
    responses={
        200: {"description": "Access and refresh tokens returned"},
        400: {"description": "Invalid or expired token"},
    },
)
async def verify_magic_link(
    request: Request,
    token: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Verify a magic link token and return JWT tokens."""
    import secrets

    from app.core.config import settings
    from app.crud.user import user as crud_user
    from app.models.user import User

    payload = decode_magic_link_token(token)
    email = payload["sub"]

    user = await crud_user.get_by_email(db, email=email)
    if not user:
        if not settings.MAGIC_LINK_ALLOW_REGISTRATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found. Registration via magic link is disabled.",
            )
        email_prefix = email.split("@")[0]
        safe_prefix = "".join(c for c in email_prefix if c.isalnum() or c in "._-")
        username = f"{safe_prefix}_{secrets.token_hex(4)}"

        user = User(
            email=email,
            username=username,
            hashed_password=secrets.token_urlsafe(32),
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.is_verified:
        user.is_verified = True
        user.email_verified_at = datetime.now(UTC)
        db.add(user)
        await db.commit()

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    access_payload = decode_access_token(access_token)
    refresh_payload = decode_refresh_token(refresh_token)
    await store_session(
        user.id,
        SessionCreatePayload(
            jti=access_payload["jti"],
            token_type="access",
            ip=ip_address,
            user_agent=user_agent,
            iat=access_payload["iat"],
            exp=access_payload["exp"],
        ),
    )
    await store_session(
        user.id,
        SessionCreatePayload(
            jti=refresh_payload["jti"],
            token_type="refresh",
            ip=ip_address,
            user_agent=user_agent,
            iat=refresh_payload["iat"],
            exp=refresh_payload["exp"],
        ),
    )

    await log_auth_event(
        db,
        event_type="magic_link_login",
        user_id=user.id,
        tenant_id=getattr(user, "tenant_id", None),
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ---------- WebAuthn / Passkey endpoints ----------


@router.post("/webauthn/register/begin")
async def webauthn_register_begin(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Begin WebAuthn passkey registration."""
    options = await begin_registration(
        user_id=str(current_user.id),
        user_name=current_user.email,
        user_display_name=current_user.full_name or current_user.email,
    )
    return options


@router.post("/webauthn/register/complete")
async def webauthn_register_complete(
    credential: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Complete WebAuthn passkey registration."""
    result = await complete_registration(
        user_id=str(current_user.id),
        credential=credential,
        db=db,
    )
    return result


@router.post("/webauthn/login/begin")
async def webauthn_login_begin(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Any:
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
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Any:
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


# ---------- JWT revocation ----------


@router.post(
    "/jwt/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke current token",
    description="Blacklist the current access token so it can no longer be used.",
)
async def revoke_token(
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    payload = decode_access_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp", 0)
    if jti:
        await revoke_session(current_user.id, jti, exp)

    client_host = getattr(request.client, "host", None) if request.client else None
    await log_auth_event(
        db,
        event_type="token_revoke",
        user_id=current_user.id,
        tenant_id=getattr(current_user, "tenant_id", None),
        ip_address=client_host,
        user_agent=request.headers.get("user-agent"),
        details={"jti": jti, "purpose": payload.get("purpose")} if jti else {},
    )
    return {"detail": "Token revoked"}


@router.post(
    "/jwt/revoke-all",
    status_code=status.HTTP_200_OK,
    summary="Revoke all tokens",
    description="Revoke every access and refresh token issued to the current user.",
)
async def revoke_all_tokens(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    count = await revoke_all_user_sessions(current_user.id)

    client_host = getattr(request.client, "host", None) if request.client else None
    await log_auth_event(
        db,
        event_type="token_revoke",
        user_id=current_user.id,
        tenant_id=getattr(current_user, "tenant_id", None),
        ip_address=client_host,
        user_agent=request.headers.get("user-agent"),
        details={"count": count, "all_tokens": True},
    )
    return {"detail": f"All {count} tokens revoked"}


# ---------- Session management ----------


@router.get(
    "/sessions",
    summary="List active sessions",
    description="Return all active sessions for the current user.",
)
async def list_sessions_endpoint(
    current_user: User = Depends(get_current_user),
) -> Any:
    sessions = await list_active_sessions(current_user.id)
    return {"sessions": sessions}


@router.post(
    "/sessions/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke a session",
    description="Revoke a specific session by its JTI.",
)
async def revoke_session_endpoint(
    request: Request,
    jti: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if not jti:
        raise HTTPException(status_code=400, detail="jti is required")
    session_data = await get_session(current_user.id, jti)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    exp = int(session_data.get("expires_at", 0))
    await revoke_session(current_user.id, jti, exp)
    client_host = getattr(request.client, "host", None) if request.client else None
    await log_auth_event(
        db,
        event_type="token_revoke",
        user_id=current_user.id,
        tenant_id=getattr(current_user, "tenant_id", None),
        ip_address=client_host,
        user_agent=request.headers.get("user-agent"),
        details={"jti": jti, "via": "sessions/revoke"},
    )
    return {"detail": "Session revoked"}


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
