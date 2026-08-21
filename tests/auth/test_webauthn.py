"""Unit tests for WebAuthn helper functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.identity.auth.webauthn import (
    _pending_registrations,
    begin_authentication,
    begin_registration,
    complete_authentication,
    complete_registration,
)


@pytest.mark.asyncio
async def test_begin_registration():
    with (
        patch("app.identity.auth.webauthn.generate_registration_options"),
        patch("app.identity.auth.webauthn._options_to_dict") as mock_opt,
    ):
        mock_opt.return_value = {"rp": {"name": "Test"}}
        result = await begin_registration("1", "test@test.com", "Test User")
    assert "rp" in result


@pytest.mark.asyncio
async def test_complete_registration_missing_session():
    _pending_registrations.clear()  # ← remove leaked state
    db = AsyncMock()
    with pytest.raises(Exception) as exc:
        await complete_registration("1", {"rawId": "abc"}, db=db)
    assert "Registration session not found" in str(exc.value)


@pytest.mark.asyncio
async def test_begin_authentication_no_credentials():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_scalars.all.return_value = []
    db.execute.return_value = mock_result

    with pytest.raises(Exception) as exc:
        await begin_authentication("1", db=db)
    assert "No registered passkeys" in str(exc.value)


@pytest.mark.asyncio
async def test_complete_authentication_missing_session():
    db = AsyncMock()
    with pytest.raises(Exception) as exc:
        await complete_authentication("1", {"rawId": "abc"}, db=db)
    assert "Authentication session not found" in str(exc.value)
