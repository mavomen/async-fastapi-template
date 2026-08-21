"""TOTP / 2FA Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class TOTPEnableResponse(BaseModel):
    secret: str
    uri: str
    backup_codes: list[str]


class TOTPVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class TOTPVerifyEnableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class TOTPDisableRequest(BaseModel):
    password: str


class TOTPStatusResponse(BaseModel):
    enabled: bool
    totp_verified_at: datetime | None = None


class TOTPLoginVerifyRequest(BaseModel):
    challenge_token: str
    code: str = Field(..., min_length=6, max_length=6)
