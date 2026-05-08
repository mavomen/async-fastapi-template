"""Multi‑tenant context and Row‑Level Security helpers."""

from contextvars import ContextVar
from typing import Optional

current_tenant_id: ContextVar[Optional[int]] = ContextVar(
    "current_tenant_id", default=None
)


def set_current_tenant(tenant_id: int | None) -> None:
    """Set the tenant ID for the current request."""
    current_tenant_id.set(tenant_id)


def get_current_tenant() -> int | None:
    """Get the current tenant ID."""
    return current_tenant_id.get()
