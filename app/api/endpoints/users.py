"""User management endpoints with RBAC protection."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.permissions import PermissionChecker
from app.crud.user import user as crud_user
from app.models.user import User
from app.schemas.user import UserDetailResponse, UserUpdate

router = APIRouter()


@router.get(
    "/",
    response_model=list[UserDetailResponse],
    summary="List all users",
    description="Retrieve a paginated list of all users. Requires `user:read` permission.",
    responses={
        200: {"description": "List of users with roles"},
        403: {"description": "Not enough permissions"},
    },
)
@router.get("/", response_model=list[UserDetailResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["user:read"])),
) -> Any:
    """List all users (requires 'user:read' permission)."""
    users = await crud_user.get_multi_with_roles(db, skip=0, limit=100)
    return users


@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Get a single user",
    description="Retrieve a specific user by ID with roles. Requires `user:read` permission.",
    responses={
        200: {"description": "User details with roles"},
        403: {"description": "Not enough permissions"},
        404: {"description": "User not found"},
    },
)
@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["user:read"])),
) -> Any:
    """Get a user by ID (requires 'user:read' permission)."""
    user = await crud_user.get_with_roles(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Update a user",
    description="Update a user’s details. Requires `user:write` permission.",
    responses={
        200: {"description": "Updated user with roles"},
        403: {"description": "Not enough permissions"},
        404: {"description": "User not found"},
        422: {"description": "Validation error"},
    },
)
@router.patch("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["user:write"])),
) -> Any:
    """Update a user (requires 'user:write' permission)."""
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updated_user = await crud_user.update(db, db_obj=user, obj_in=user_in)
    # Reload with roles after update to return complete data
    return await crud_user.get_with_roles(db, id=updated_user.id)


@router.delete(
    "/{user_id}",
    response_model=dict,
    summary="Delete a user",
    description="Delete a user by ID. Requires `user:delete` permission.",
    responses={
        200: {"description": "User deleted successfully"},
        403: {"description": "Not enough permissions"},
        404: {"description": "User not found"},
    },
)
@router.delete("/{user_id}", response_model=dict)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["user:delete"])),
) -> Any:
    """Delete a user (requires 'user:delete' permission)."""
    user = await crud_user.delete(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "User deleted successfully"}
