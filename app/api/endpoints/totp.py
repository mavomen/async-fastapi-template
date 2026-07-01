"""API endpoints for TOTP 2FA management."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.auth.totp import (
    generate_backup_codes,
    generate_totp_secret,
    get_totp_uri,
    hash_backup_code,
    verify_totp_code,
)
from app.core.security import verify_password
from app.models.user import User
from app.schemas.totp import (
    TOTPDisableRequest,
    TOTPEnableResponse,
    TOTPStatusResponse,
    TOTPVerifyEnableRequest,
)
from app.services.auth_audit import log_auth_event

router = APIRouter()


@router.get(
    "/totp/status",
    response_model=TOTPStatusResponse,
    summary="Get TOTP status",
    description="Return whether TOTP 2FA is enabled for the current user.",
)
async def get_totp_status(
    current_user: User = Depends(get_current_user),
) -> Any:
    return TOTPStatusResponse(
        enabled=current_user.totp_enabled,
        totp_verified_at=current_user.totp_verified_at,
    )


@router.post(
    "/totp/enable",
    response_model=TOTPEnableResponse,
    summary="Enable TOTP 2FA",
    description="Generate a TOTP secret and provisioning URI. "
    "The user must then POST /totp/verify-enable with a valid code to activate 2FA.",
)
async def enable_totp(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is already enabled",
        )
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, current_user.email)
    raw_codes = generate_backup_codes()
    hashed_codes = ",".join(hash_backup_code(c) for c in raw_codes)

    current_user.totp_secret = secret
    current_user.backup_codes = hashed_codes
    current_user.totp_enabled = False  # not yet confirmed
    db.add(current_user)
    await db.commit()

    return TOTPEnableResponse(
        secret=secret,
        uri=uri,
        backup_codes=raw_codes,
    )


@router.post(
    "/totp/verify-enable",
    status_code=status.HTTP_200_OK,
    summary="Confirm TOTP setup",
    description="Verify a TOTP code to activate 2FA after calling POST /totp/enable.",
)
async def verify_enable_totp(
    body: TOTPVerifyEnableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is already enabled",
        )
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending TOTP setup. Call POST /totp/enable first.",
        )
    if not verify_totp_code(current_user.totp_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )
    current_user.totp_enabled = True
    current_user.totp_verified_at = datetime.now(UTC)
    db.add(current_user)
    await db.commit()

    await log_auth_event(
        db,
        event_type="mfa_enroll",
        user_id=current_user.id,
        tenant_id=getattr(current_user, "tenant_id", None),
    )

    return {"detail": "TOTP 2FA enabled successfully"}


@router.post(
    "/totp/disable",
    status_code=status.HTTP_200_OK,
    summary="Disable TOTP 2FA",
    description="Disable TOTP 2FA after confirming the current password.",
)
async def disable_totp(
    body: TOTPDisableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if not current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is not currently enabled",
        )
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password",
        )
    current_user.totp_secret = None
    current_user.totp_enabled = False
    current_user.totp_verified_at = None
    current_user.backup_codes = None
    db.add(current_user)
    await db.commit()

    await log_auth_event(
        db,
        event_type="mfa_disable",
        user_id=current_user.id,
        tenant_id=getattr(current_user, "tenant_id", None),
    )

    return {"detail": "TOTP 2FA disabled successfully"}
