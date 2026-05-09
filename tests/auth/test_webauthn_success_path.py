"""Happy-path WebAuthn tests using mocked webauthn library."""

from unittest.mock import MagicMock, patch

import pytest

from app.auth.webauthn import (
    begin_authentication,
    complete_authentication,
    complete_registration,
)


@pytest.mark.asyncio
async def test_complete_registration_success():
    """Complete a registration successfully (mocked)."""
    from app.auth.webauthn import _pending_registrations

    # Arrange: place a fake pending challenge
    fake_options = MagicMock()
    fake_options.challenge = b"fake-challenge"
    _pending_registrations["user-1"] = fake_options

    with patch("app.auth.webauthn.verify_registration_response") as mock_verify:
        mock_verify.return_value = MagicMock(
            credential_id="cred-1",
            credential_public_key="pub-key",
            sign_count=0,
        )
        result = await complete_registration("user-1", {"rawId": "abc"})
    assert result["status"] == "ok"
    assert result["credential_id"] == "cred-1"


@pytest.mark.asyncio
async def test_complete_authentication_success():
    """Complete an authentication successfully (mocked)."""
    from app.auth.webauthn import _pending_authentications, _user_credentials

    # Arrange: store a credential and a pending challenge
    _user_credentials["user-2"] = [
        {"credential_id": "cred-2", "credential_public_key": "pub-key", "sign_count": 0}
    ]
    fake_options = MagicMock()
    fake_options.challenge = b"fake-challenge"
    _pending_authentications["user-2"] = fake_options

    with patch("app.auth.webauthn.verify_authentication_response"):
        result = await complete_authentication("user-2", {"rawId": "abc"})
    assert result is True


@pytest.mark.asyncio
async def test_begin_authentication_success():
    """Begin authentication with stored credentials succeeds."""
    from app.auth.webauthn import _user_credentials

    _user_credentials["user-3"] = [
        {"credential_id": "cred-3", "credential_public_key": "pub-key", "sign_count": 0}
    ]
    with (
        patch("app.auth.webauthn.generate_authentication_options") as mock_gen,
        patch("app.auth.webauthn._options_to_dict") as mock_opt,
    ):
        fake_options = MagicMock()
        fake_options.model_dump_json.return_value = '{"challenge":"def"}'
        mock_gen.return_value = fake_options
        mock_opt.return_value = {"challenge": "def"}
        result = await begin_authentication("user-3")
    assert "challenge" in result
