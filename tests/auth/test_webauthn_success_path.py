"""Happy‑path WebAuthn tests using mocked DB."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.webauthn import (
    begin_authentication,
    complete_authentication,
    complete_registration,
)
from app.models.webauthn_credential import WebAuthnCredential


# Helper to build a proper async mock for db.execute
def _mock_db_execute(return_creds: list):
    """Return an AsyncMock whose execute() returns a mock with scalars().all() → return_creds."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_scalars.all.return_value = return_creds
    db.execute.return_value = mock_result
    return db


@pytest.mark.asyncio
async def test_complete_registration_success():
    from app.auth.webauthn import _pending_registrations

    fake_options = MagicMock()
    fake_options.challenge = b"fake-challenge"
    _pending_registrations["1"] = fake_options

    db = AsyncMock()
    with patch("app.auth.webauthn.verify_registration_response") as mock_verify:
        mock_verify.return_value = MagicMock(
            credential_id="cred-1",
            credential_public_key="pub-key",
            sign_count=0,
        )
        result = await complete_registration("1", {"rawId": "abc"}, db=db)
    assert result["status"] == "ok"
    assert result["credential_id"] == "cred-1"


@pytest.mark.asyncio
async def test_complete_authentication_success():
    from app.auth.webauthn import _pending_authentications

    fake_options = MagicMock()
    fake_options.challenge = b"fake-challenge"
    _pending_authentications["2"] = fake_options

    db_cred = MagicMock(spec=WebAuthnCredential)
    db_cred.credential_id = "cred-2"
    db_cred.public_key = "pub-key"
    db_cred.sign_count = 0
    db = _mock_db_execute([db_cred])

    with patch("app.auth.webauthn.verify_authentication_response"):
        result = await complete_authentication("2", {"rawId": "abc"}, db=db)
    assert result is True


@pytest.mark.asyncio
async def test_begin_authentication_success():
    db_cred = MagicMock(spec=WebAuthnCredential)
    db_cred.credential_id = "cred-3"
    db_cred.public_key = "pub-key"
    db = _mock_db_execute([db_cred])

    with (
        patch("app.auth.webauthn.generate_authentication_options") as mock_gen,
        patch("app.auth.webauthn._options_to_dict") as mock_opt,
    ):
        mock_gen.return_value = MagicMock()
        mock_opt.return_value = {"challenge": "def"}
        result = await begin_authentication("3", db=db)
    assert "challenge" in result
