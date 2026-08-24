"""API endpoints for managing the billing plan catalog.

Plan management is admin-gated via ``billing:write``. ``currency`` and
``interval`` are immutable on existing plans (see PlanUpdate).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.billing.crud.plan import plan as crud_plan
from app.billing.models.plan import Plan
from app.billing.schemas.plan import PlanCreate, PlanListResponse, PlanResponse, PlanUpdate
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.identity.auth.permissions import PermissionChecker
from app.identity.models.user import User

router = APIRouter()


@router.get(
    "",
    response_model=PlanListResponse,
    summary="List active plans",
)
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlanListResponse:
    items = await crud_plan.list_active(db)
    return PlanListResponse(items=[PlanResponse.model_validate(p) for p in items])


@router.post(
    "",
    response_model=PlanResponse,
    status_code=201,
    summary="Create a plan",
    dependencies=[Depends(PermissionChecker(["billing:write"]))],
)
async def create_plan(
    obj_in: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Plan:
    if await crud_plan.get_by_slug(db, slug=obj_in.slug) is not None:
        raise ConflictException(detail=f"Plan slug '{obj_in.slug}' already exists")
    return await crud_plan.create(db, obj_in)


@router.patch(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Update a plan (price/name/trial/active only)",
    dependencies=[Depends(PermissionChecker(["billing:write"]))],
)
async def update_plan(
    plan_id: int,
    obj_in: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Plan:
    plan_obj = await crud_plan.get(db, plan_id)
    if plan_obj is None:
        raise NotFoundException(detail="Plan not found")
    return await crud_plan.update(db, plan_obj, obj_in)


@router.delete(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Deactivate a plan",
    dependencies=[Depends(PermissionChecker(["billing:write"]))],
)
async def deactivate_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Plan:
    """Soft-deactivation: plans with subscribers must not vanish; we flag instead."""
    plan_obj = await crud_plan.get(db, plan_id)
    if plan_obj is None:
        raise NotFoundException(detail="Plan not found")
    if not plan_obj.is_active:
        raise BadRequestException(detail="Plan is already inactive")
    return await crud_plan.update(db, plan_obj, PlanUpdate(is_active=False))
