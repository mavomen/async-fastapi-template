"""Identity domain Pydantic schemas."""

from app.identity.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyResponse,
    ApiKeyUpdate,
)
from app.identity.schemas.oauth import OAuthLoginResponse, OAuthProviderInfo
from app.identity.schemas.role import PermissionRead, RoleRead
from app.identity.schemas.tenant import TenantCreate
from app.identity.schemas.tenant_ip_rule import (
    IPRuleCreate,
    IPRuleResponse,
    IPRuleUpdate,
)
from app.identity.schemas.token import Token, TokenPayload
from app.identity.schemas.totp import (
    TOTPDisableRequest,
    TOTPEnableResponse,
    TOTPLoginVerifyRequest,
    TOTPStatusResponse,
    TOTPVerifyEnableRequest,
    TOTPVerifyRequest,
)
from app.identity.schemas.user import UserCreate, UserInDB, UserResponse, UserUpdate

__all__ = [
    "ApiKeyCreate",
    "ApiKeyCreated",
    "ApiKeyResponse",
    "ApiKeyUpdate",
    "IPRuleCreate",
    "IPRuleResponse",
    "IPRuleUpdate",
    "OAuthLoginResponse",
    "OAuthProviderInfo",
    "PermissionRead",
    "RoleRead",
    "TOTPDisableRequest",
    "TOTPEnableResponse",
    "TOTPLoginVerifyRequest",
    "TOTPStatusResponse",
    "TOTPVerifyEnableRequest",
    "TOTPVerifyRequest",
    "TenantCreate",
    "Token",
    "TokenPayload",
    "UserCreate",
    "UserInDB",
    "UserResponse",
    "UserUpdate",
]
