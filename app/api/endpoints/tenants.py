"""Tenant management endpoints (superuser only)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_read_db
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate

router = APIRouter()


@router.post("/")
async def create_tenant(
    tenant_in: TenantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new tenant (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")

    tenant = Tenant(name=tenant_in.name, slug=tenant_in.slug)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return {"id": tenant.id, "name": tenant.name, "slug": tenant.slug}


@router.get("/")
async def list_tenants(
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all tenants (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")

    result = await db.execute(select(Tenant))
    return [
        {"id": t.id, "name": t.name, "slug": t.slug, "is_active": t.is_active}
        for t in result.scalars().all()
    ]
