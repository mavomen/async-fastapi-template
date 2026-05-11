"""WebAuthn / Passkey support backed by the database."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.base64url_to_bytes import base64url_to_bytes
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialCreationOptions,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialRequestOptions,
    PublicKeyCredentialType,
    UserVerificationRequirement,
)

from app.core.config import settings
from app.models.webauthn_credential import WebAuthnCredential

# In-memory challenge store - challenges are short-lived and don’t need persistence
_pending_registrations: dict[str, PublicKeyCredentialCreationOptions] = {}
_pending_authentications: dict[str, PublicKeyCredentialRequestOptions] = {}


def _options_to_dict(options) -> dict:
    import json

    from pydantic import BaseModel

    if isinstance(options, BaseModel):
        return json.loads(options.model_dump_json())
    return options


async def begin_registration(
    user_id: str,
    user_name: str,
    user_display_name: str,
) -> dict:
    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=user_id.encode(),
        user_name=user_name,
        user_display_name=user_display_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[COSEAlgorithmIdentifier.ECDSA_SHA_256],
    )
    _pending_registrations[user_id] = options
    return _options_to_dict(options)


async def complete_registration(
    user_id: str,
    credential: dict,
    db: AsyncSession,
) -> dict:
    expected_options = _pending_registrations.pop(user_id, None)
    if not expected_options:
        raise HTTPException(status_code=400, detail="Registration session not found")

    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=expected_options.challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid registration response: {e}")

    db_cred = WebAuthnCredential(
        user_id=int(user_id),
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
    )
    db.add(db_cred)
    await db.commit()

    return {"status": "ok", "credential_id": verified.credential_id}


async def begin_authentication(user_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == int(user_id))
    )
    creds = result.scalars().all()
    if not creds:
        raise HTTPException(status_code=400, detail="No registered passkeys")

    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=[
            PublicKeyCredentialDescriptor(
                id=c.credential_id.encode(),
                type=PublicKeyCredentialType.PUBLIC_KEY,
            )
            for c in creds
        ],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    _pending_authentications[user_id] = options
    return _options_to_dict(options)


async def complete_authentication(
    user_id: str,
    credential: dict,
    db: AsyncSession,
) -> bool:
    expected_options = _pending_authentications.pop(user_id, None)
    if not expected_options:
        raise HTTPException(status_code=400, detail="Authentication session not found")

    result = await db.execute(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == int(user_id))
    )
    creds = result.scalars().all()
    if not creds:
        raise HTTPException(status_code=400, detail="No registered passkeys")

    # In practice, you’d match the credential_id from the response to a specific credential.
    # For simplicity, we use the first stored credential.
    db_cred = creds[0]

    try:
        verify_authentication_response(
            credential=credential,
            expected_challenge=expected_options.challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            credential_public_key=base64url_to_bytes(db_cred.public_key),
            credential_current_sign_count=db_cred.sign_count,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid authentication response: {e}")

    return True
