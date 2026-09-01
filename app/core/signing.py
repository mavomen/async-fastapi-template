"""HMAC signature helpers for webhook payloads.

Shared by the notifications context (outgoing webhooks) and the billing
context (inbound Stripe webhooks, whose ``t=...,v1=`` scheme is identical:
HMAC-SHA256 over ``"{timestamp}.{body}"``).
"""

import hashlib
import hmac
import time

from app.core.config import settings


def sign_payload(body: bytes, secret: str, timestamp: int) -> str:
    """Sign a request body with HMAC-SHA256, binding it to a timestamp."""
    message = f"{timestamp}.{body.decode()}".encode()
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def build_signature_header(body: bytes, secret: str, timestamp: int) -> str:
    """Build the ``t=<ts>,v1=<sig>`` signature header value for a payload."""
    return f"t={timestamp},v1={sign_payload(body, secret, timestamp)}"


def verify_signature_header(
    body: bytes,
    secret: str,
    signature_header: str | None,
    *,
    tolerance_seconds: int | None = None,
) -> bool:
    """Verify a ``t=<ts>,v1=<sig>`` signature header, rejecting stale timestamps."""
    if not signature_header:
        return False
    parts: dict[str, str] = {}
    for item in signature_header.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()
    timestamp_str = parts.get("t")
    signature = parts.get("v1")
    if not timestamp_str or not signature:
        return False
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False
    tolerance = (
        tolerance_seconds
        if tolerance_seconds is not None
        else settings.WEBHOOK_SIGNATURE_TOLERANCE_SECONDS
    )
    if abs(int(time.time()) - timestamp) > tolerance:
        return False
    expected = sign_payload(body, secret, timestamp)
    return hmac.compare_digest(expected, signature)
