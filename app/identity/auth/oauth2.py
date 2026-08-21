"""OAuth2 social login utilities for Google, GitHub, GitLab."""

import secrets
from typing import Any

from app.core.config import settings
from app.core.http_client import http_client

OAUTH_PROVIDER_META: dict[str, dict[str, Any]] = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": ["openid", "email", "profile"],
        "email_key": "email",
        "name_key": "name",
        "id_key": "id",
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scopes": ["read:user", "user:email"],
        "email_key": "email",
        "name_key": "name",
        "id_key": "id",
    },
    "gitlab": {
        "authorize_url": "https://gitlab.com/oauth/authorize",
        "token_url": "https://gitlab.com/oauth/token",
        "userinfo_url": "https://gitlab.com/api/v4/user",
        "scopes": ["read_user", "openid"],
        "email_key": "email",
        "name_key": "name",
        "id_key": "id",
    },
}

OAUTH_STATE_KEY_PREFIX = "oauth_state:"

# Mapping from provider name to settings field names
_OAUTH_SETTINGS_FIELDS: dict[str, dict[str, str]] = {
    "google": {
        "client_id": "GOOGLE_CLIENT_ID",
        "client_secret": "GOOGLE_CLIENT_SECRET",
    },
    "github": {
        "client_id": "GITHUB_CLIENT_ID",
        "client_secret": "GITHUB_CLIENT_SECRET",
    },
    "gitlab": {
        "client_id": "GITLAB_CLIENT_ID",
        "client_secret": "GITLAB_CLIENT_SECRET",
    },
}


def _get_client_credentials(provider: str) -> tuple[str, str]:
    """Get client_id and client_secret from settings for the given provider."""
    fields = _OAUTH_SETTINGS_FIELDS.get(provider)
    if not fields:
        raise ValueError(f"Unsupported OAuth provider: {provider}")
    client_id = getattr(settings, fields["client_id"], "")
    client_secret = getattr(settings, fields["client_secret"], "")
    if not client_id or not client_secret:
        raise ValueError(
            f"OAuth provider '{provider}' is not configured (missing {fields['client_id']} or {fields['client_secret']})"
        )
    return client_id, client_secret


def get_provider_meta(provider: str) -> dict[str, Any]:
    """Return provider metadata (URLs, scopes, keys) or raise ValueError."""
    meta = OAUTH_PROVIDER_META.get(provider)
    if not meta:
        raise ValueError(f"Unsupported OAuth provider: {provider}")
    return meta


def get_authorize_url(provider: str, state: str, redirect_uri: str) -> str:
    """Build the OAuth2 authorize URL for the given provider."""
    meta = get_provider_meta(provider)
    client_id, _ = _get_client_credentials(provider)
    scope = " ".join(meta["scopes"])
    return (
        f"{meta['authorize_url']}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
        f"&state={state}"
        f"&response_type=code"
    )


async def exchange_code(provider: str, code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code for access/refresh tokens."""
    meta = get_provider_meta(provider)
    client_id, client_secret = _get_client_credentials(provider)
    client = http_client.get_client()
    resp = await client.post(
        meta["token_url"],
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


async def get_user_info(provider: str, access_token: str) -> dict[str, Any]:
    """Fetch user info from the provider's userinfo endpoint."""
    meta = get_provider_meta(provider)
    client = http_client.get_client()
    resp = await client.get(
        meta["userinfo_url"],
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def parse_user_info(provider: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Extract normalized user info from raw provider response.

    Returns dict with keys: email, name, provider_id
    """
    meta = get_provider_meta(provider)
    email = raw.get(meta["email_key"], "")
    name = raw.get(meta["name_key"], "")
    provider_id = str(raw.get(meta["id_key"], ""))
    return {"email": email, "name": name, "provider_id": provider_id}


def generate_oauth_state() -> str:
    """Generate a cryptographically random state string for CSRF protection."""
    return secrets.token_urlsafe(32)
