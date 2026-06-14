"""Middleware that resolves the current tenant from subdomain or header."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import sessionmanager
from app.core.tenant import set_current_tenant


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve tenant from X-Tenant-ID header; safe when tenants table is absent."""

    _default_tenant_id: int | None = None

    @classmethod
    async def warm_default_tenant(cls) -> None:
        """Pre-warm the default tenant cache at startup to avoid a DB query on the first request."""
        if cls._default_tenant_id is not None:
            return
        try:
            from sqlalchemy import select

            from app.models.tenant import Tenant

            async with sessionmanager.session() as db:
                result = await db.execute(select(Tenant.id).where(Tenant.is_active).limit(1))
                row = result.scalar_one_or_none()
                if row:
                    cls._default_tenant_id = row
        except Exception:
            pass

    async def dispatch(self, request: Request, call_next):
        tenant_id = None

        header_value = request.headers.get("X-Tenant-ID")
        if header_value and header_value.isdigit():
            tenant_id = int(header_value)

        if tenant_id is None:
            cached = type(self)._default_tenant_id
            if cached is not None:
                tenant_id = cached

        set_current_tenant(tenant_id)
        response = await call_next(request)
        set_current_tenant(None)
        return response
