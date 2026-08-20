"""API endpoints for managing API keys."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.auth.permissions import PermissionChecker
from app.crud.api_key import api_key as crud_api_key
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyResponse, ApiKeyUpdate

router = APIRouter()


@router.post(
    "/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
    description="Create a new API key for the current user. "
    "The raw key is returned only once in the response.",
)
async def create_api_key(
    *,
    db: AsyncSession = Depends(get_db),
    obj_in: ApiKeyCreate,
    current_user: User = Depends(PermissionChecker(["api_key:write"])),
) -> Any:
    api_key_obj, raw_key = await crud_api_key.create_with_raw_key(
        db, user_id=current_user.id, obj_in=obj_in
    )
    return ApiKeyCreated(
        id=api_key_obj.id,
        name=api_key_obj.name,
        key_prefix=api_key_obj.key_prefix,
        scopes=api_key_obj.scopes,
        is_active=api_key_obj.is_active,
        last_used_at=api_key_obj.last_used_at,
        expires_at=api_key_obj.expires_at,
        created_at=api_key_obj.created_at,
        updated_at=api_key_obj.updated_at,
        raw_key=raw_key,
    )


@router.get(
    "/api-keys",
    response_model=list[ApiKeyResponse],
    summary="List API keys",
    description="List all API keys for the current user.",
)
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    return await crud_api_key.get_active_for_user(db, user_id=current_user.id)


@router.patch(
    "/api-keys/{api_key_id}",
    response_model=ApiKeyResponse,
    summary="Update API key",
    description="Update name, scopes, or active status of an API key.",
)
async def update_api_key(
    api_key_id: int,
    *,
    db: AsyncSession = Depends(get_db),
    obj_in: ApiKeyUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    api_key_obj = await crud_api_key.get(db, id=api_key_id)
    if api_key_obj is None or api_key_obj.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    result = await crud_api_key.update(db, db_obj=api_key_obj, obj_in=obj_in)
    return result


@router.delete(
    "/api-keys/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete API key",
    description="Delete (soft-delete) an API key.",
)
async def delete_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    api_key_obj = await crud_api_key.get(db, id=api_key_id)
    if api_key_obj is None or api_key_obj.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    await crud_api_key.delete(db, id=api_key_id)


@router.post(
    "/api-keys/{api_key_id}/restore",
    response_model=ApiKeyResponse,
    summary="Restore API key",
    description="Restore a soft-deleted API key.",
)
async def restore_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    api_key_obj = await crud_api_key.restore(db, id=api_key_id)
    if api_key_obj is None or api_key_obj.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deleted API key not found")
    return api_key_obj
