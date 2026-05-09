"""Unit tests for WebAuthn helper functions."""

from unittest.mock import patch

import pytest

from app.auth.webauthn import (
    begin_authentication,
    begin_registration,
    complete_authentication,
    complete_registration,
)


@pytest.mark.asyncio
async def test_begin_registration():
    with (
        patch("app.auth.webauthn.generate_registration_options"),
        patch("app.auth.webauthn._options_to_dict") as mock_opt,
    ):
        mock_opt.return_value = {"rp": {"name": "Test"}}
        result = await begin_registration("user-1", "test@test.com", "Test User")
    assert "rp" in result


@pytest.mark.asyncio
async def test_complete_registration_missing_session():
    with pytest.raises(Exception) as exc:
        await complete_registration("nonexistent", {"rawId": "abc"})
    assert "Registration session not found" in str(exc.value)


@pytest.mark.asyncio
async def test_begin_authentication_no_credentials():
    with pytest.raises(Exception) as exc:
        await begin_authentication("user-no-creds")
    assert "No registered passkeys" in str(exc.value)


@pytest.mark.asyncio
async def test_complete_authentication_missing_session():
    with pytest.raises(Exception) as exc:
        await complete_authentication("nonexistent", {"rawId": "abc"})
    assert "Authentication session not found" in str(exc.value)
