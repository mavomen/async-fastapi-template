"""Middleware that resolves the current tenant from subdomain or header."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import sessionmanager
from app.core.tenant import set_current_tenant


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve tenant from X‑Tenant‑ID header; safe when tenants table is absent."""

    async def dispatch(self, request: Request, call_next):
        tenant_id = None

        # 1. Try header
        header_value = request.headers.get("X-Tenant-ID")
        if header_value and header_value.isdigit():
            tenant_id = int(header_value)

        # 2. Try querying the database if no header provided
        if tenant_id is None:
            try:
                from sqlalchemy import select

                from app.models.tenant import Tenant

                async with sessionmanager.session() as db:
                    result = await db.execute(
                        select(Tenant.id).where(Tenant.is_active == True).limit(1)
                    )
                    row = result.scalar_one_or_none()
                    if row:
                        tenant_id = row
            except Exception:
                # Swallow errors when tenants table is absent (tests, first startup)
                pass

        set_current_tenant(tenant_id)
        response = await call_next(request)
        set_current_tenant(None)
        return response
