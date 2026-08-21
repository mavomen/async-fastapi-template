"""Tenant IP rule management endpoints (superuser only)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.identity.crud.tenant_ip_rule import tenant_ip_rule as crud_ip_rule
from app.identity.models.user import User
from app.identity.schemas.tenant_ip_rule import IPRuleCreate, IPRuleResponse, IPRuleUpdate

router = APIRouter()


@router.post("/tenant-ip-rules", response_model=IPRuleResponse)
async def create_ip_rule(
    rule_in: IPRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new IP allow/deny rule (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")

    rule = await crud_ip_rule.create(
        db,
        tenant_id=rule_in.tenant_id,
        ip_or_cidr=rule_in.ip_or_cidr,
        action=rule_in.action,
        priority=rule_in.priority,
        description=rule_in.description,
    )
    return IPRuleResponse(
        id=rule.id,
        tenant_id=rule.tenant_id,
        ip_or_cidr=rule.ip_or_cidr,
        action=rule.action,
        priority=rule.priority,
        description=rule.description,
    )


@router.get("/tenant-ip-rules", response_model=list[IPRuleResponse])
async def list_ip_rules(
    tenant_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List IP rules, optionally filtered by tenant (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")

    if tenant_id is not None:
        rules = await crud_ip_rule.get_multi_by_tenant(
            db, tenant_id=tenant_id, skip=skip, limit=limit
        )
    else:
        rules = []

    return [
        IPRuleResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            ip_or_cidr=r.ip_or_cidr,
            action=r.action,
            priority=r.priority,
            description=r.description,
        )
        for r in rules
    ]


@router.get("/tenant-ip-rules/{rule_id}", response_model=IPRuleResponse)
async def get_ip_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get a single IP rule by ID (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")

    rule = await crud_ip_rule.get(db, id=rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="IP rule not found")

    return IPRuleResponse(
        id=rule.id,
        tenant_id=rule.tenant_id,
        ip_or_cidr=rule.ip_or_cidr,
        action=rule.action,
        priority=rule.priority,
        description=rule.description,
    )


@router.put("/tenant-ip-rules/{rule_id}", response_model=IPRuleResponse)
async def update_ip_rule(
    rule_id: int,
    rule_in: IPRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update an IP rule (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")

    rule = await crud_ip_rule.get(db, id=rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="IP rule not found")

    rule = await crud_ip_rule.update(
        db,
        db_obj=rule,
        ip_or_cidr=rule_in.ip_or_cidr,
        action=rule_in.action,
        priority=rule_in.priority,
        description=rule_in.description,
    )
    return IPRuleResponse(
        id=rule.id,
        tenant_id=rule.tenant_id,
        ip_or_cidr=rule.ip_or_cidr,
        action=rule.action,
        priority=rule.priority,
        description=rule.description,
    )


@router.delete("/tenant-ip-rules/{rule_id}")
async def delete_ip_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Delete an IP rule (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")

    rule = await crud_ip_rule.remove(db, id=rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="IP rule not found")

    return {"detail": "IP rule deleted"}
