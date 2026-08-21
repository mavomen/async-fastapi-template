"""Tests for WebAuthn passkey endpoints (mocked)."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_webauthn_register_begin(async_client: AsyncClient, auth_headers: dict):
    """WebAuthn registration begin returns public key options."""
    with patch(
        "app.identity.auth.webauthn.generate_registration_options_for_user",
        return_value={"rp": {"name": "Test"}, "user": {"id": "42"}},
    ):
        resp = await async_client.post(
            "/api/v1/auth/webauthn/register/begin",
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert "rp" in resp.json()


@pytest.mark.asyncio
async def test_webauthn_login_begin(async_client: AsyncClient):
    """WebAuthn login begin returns authentication options."""
    with patch(
        "app.identity.auth.webauthn.generate_authentication_options",
        return_value={"challenge": "abc", "allowCredentials": []},
    ):
        resp = await async_client.post(
            "/api/v1/auth/webauthn/login/begin",
            json={"user_id": "test@example.com"},
        )
    assert resp.status_code == 200
    assert "challenge" in resp.json()
