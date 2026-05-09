"""WebAuthn / Passkey support using the webauthn library."""

from fastapi import HTTPException
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

# In-memory challenge store (use Redis in production)
_pending_registrations: dict[str, PublicKeyCredentialCreationOptions] = {}
_pending_authentications: dict[str, PublicKeyCredentialRequestOptions] = {}

# In-memory credential store (use DB in production)
_user_credentials: dict[str, list[dict]] = {}  # user_id -> list of credential dicts


def _options_to_dict(options) -> dict:
    """Convert a Pydantic webauthn model to a plain dict for JSON responses."""
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
    """Create PublicKeyCredentialCreationOptions for a new passkey."""
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
) -> dict:
    """Verify a WebAuthn registration response and store the credential."""
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

    cred_data = {
        "credential_id": verified.credential_id,
        "credential_public_key": verified.credential_public_key,
        "sign_count": verified.sign_count,
    }
    _user_credentials.setdefault(user_id, []).append(cred_data)

    return {"status": "ok", "credential_id": verified.credential_id}


async def begin_authentication(user_id: str) -> dict:
    """Create PublicKeyCredentialRequestOptions for passkey authentication."""
    user_creds = _user_credentials.get(user_id, [])
    if not user_creds:
        raise HTTPException(status_code=400, detail="No registered passkeys")

    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=[
            PublicKeyCredentialDescriptor(
                id=c["credential_id"],
                type=PublicKeyCredentialType.PUBLIC_KEY,
            )
            for c in user_creds
        ],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    _pending_authentications[user_id] = options
    return _options_to_dict(options)


async def complete_authentication(
    user_id: str,
    credential: dict,
) -> bool:
    """Verify a WebAuthn authentication response. Returns True if successful."""
    expected_options = _pending_authentications.pop(user_id, None)
    if not expected_options:
        raise HTTPException(status_code=400, detail="Authentication session not found")

    user_creds = _user_credentials.get(user_id, [])
    if not user_creds:
        raise HTTPException(status_code=400, detail="No registered passkeys")

    try:
        verify_authentication_response(
            credential=credential,
            expected_challenge=expected_options.challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            credential_public_key=base64url_to_bytes(user_creds[0]["credential_public_key"]),
            credential_current_sign_count=user_creds[0]["sign_count"],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid authentication response: {e}")

    return True
