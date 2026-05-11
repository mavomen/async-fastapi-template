"""Tests for DB‑backed WebAuthn credential store."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.crud.user import user as crud_user
from app.models.webauthn_credential import WebAuthnCredential
from app.schemas.user import UserCreate


def _mock_db_execute(return_creds: list) -> AsyncMock:
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_scalars.all.return_value = return_creds
    db.execute.return_value = mock_result
    return db


@pytest.mark.asyncio
async def test_complete_registration_stores_credential(
    async_client: AsyncClient, db_session: AsyncSession
):
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="webauthndb@test.com", username="webauthndb", password="Password1!"
        ),
    )
    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.auth.webauthn.generate_registration_options") as mock_gen:
        mock_gen.return_value.model_dump_json.return_value = (
            '{"rp":{"name":"Test"},"challenge":"abc"}'
        )
        mock_gen.return_value.challenge = b"abc"
        await async_client.post("/api/v1/auth/webauthn/register/begin", headers=headers)

    with patch("app.auth.webauthn.verify_registration_response") as mock_verify:
        mock_verify.return_value = MagicMock(
            credential_id="cred-1", credential_public_key="pubkey", sign_count=0
        )
        await async_client.post(
            "/api/v1/auth/webauthn/register/complete",
            json={"rawId": "abc", "response": {}},
            headers=headers,
        )

    result = await db_session.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)
    )
    creds = result.scalars().all()
    assert len(creds) >= 1
    assert creds[0].credential_id == "cred-1"
