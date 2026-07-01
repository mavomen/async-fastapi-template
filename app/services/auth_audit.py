"""Auth audit event logging service."""

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_audit_log import AUTH_EVENT_TYPES, AuthAuditLog


def _validate_event_type(event_type: str) -> None:
    if event_type not in AUTH_EVENT_TYPES:
        msg = f"Invalid auth event type: {event_type!r}. Must be one of {sorted(AUTH_EVENT_TYPES)}"
        raise ValueError(msg)


async def log_auth_event(  # noqa: PLR0913
    db: AsyncSession,
    *,
    event_type: str,
    user_id: int | None = None,
    tenant_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuthAuditLog:
    """Persist an authentication event to the audit log."""
    _validate_event_type(event_type)

    entry = AuthAuditLog(
        event_type=event_type,
        user_id=user_id,
        tenant_id=tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=json.dumps(details) if details else None,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry
