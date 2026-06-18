"""User management endpoints with RBAC protection and data export."""

import csv
import io
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_read_db
from app.auth.permissions import PermissionChecker
from app.crud.user import user as crud_user
from app.models.user import User
from app.schemas.user import UserCreate, UserDetailResponse, UserUpdate
from app.utils.export_csv import export_to_csv
from app.utils.export_excel import export_to_excel

router = APIRouter()


@router.get(
    "/",
    response_model=list[UserDetailResponse],
    summary="List all users",
    description="Retrieve a paginated list of all users. Requires `user:read` permission.",
    responses={
        200: {"description": "List of users with roles"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
    },
)
async def list_users(
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(PermissionChecker(["user:read"])),
) -> Any:
    """List all users (requires 'user:read' permission)."""
    return await crud_user.get_multi_with_roles(db, skip=0, limit=100)


@router.get(
    "/export",
    response_class=Response,
    summary="Export users",
    description="Export all users as CSV or Excel. Requires `user:read` permission.",
    responses={
        200: {"description": "Exported file"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
    },
)
async def export_users(
    format: str = Query("csv", enum=["csv", "excel"]),
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(PermissionChecker(["user:read"])),
) -> Any:
    """Export all users as CSV or Excel (requires user:read)."""
    users = await crud_user.get_multi(db, skip=0, limit=10000)
    columns = [
        "id",
        "email",
        "username",
        "full_name",
        "is_active",
        "is_verified",
        "created_at",
    ]
    data = [
        {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat() if u.created_at else "",
        }
        for u in users
    ]

    if format == "excel":
        content: str | bytes = export_to_excel(data, columns)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "users.xlsx"
    else:
        content = export_to_csv(data, columns)
        media_type = "text/csv"
        filename = "users.csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Get a single user",
    description="Retrieve a specific user by ID with roles. Requires `user:read` permission.",
    responses={
        200: {"description": "User details with roles"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        404: {"description": "User not found"},
    },
)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_read_db),
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
    description="Update a user's details. Requires `user:write` permission.",
    responses={
        200: {"description": "Updated user with roles"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        404: {"description": "User not found"},
        422: {"description": "Validation error"},
    },
)
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
    return await crud_user.get_with_roles(db, id=updated_user.id)


@router.delete(
    "/{user_id}",
    response_model=dict,
    summary="Delete a user",
    description="Delete a user by ID. Requires `user:delete` permission.",
    responses={
        200: {"description": "User deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        404: {"description": "User not found"},
    },
)
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


@router.post(
    "/bulk",
    response_model=list[UserDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_users(
    users: list[UserCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["user:write"])),
) -> Any:
    """Create multiple users in one request (requires user:write)."""
    created = []
    for user_in in users:
        user = await crud_user.create(db, obj_in=user_in)
        created.append(user)
    return created


@router.post(
    "/import/csv",
    response_model=list[UserDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def import_users_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["user:write"])),
) -> Any:
    """Import users from a CSV file (requires user:write)."""
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode()))
    created = []
    for row in reader:
        user_in = UserCreate(
            email=row["email"],
            username=row["username"],
            password=row["password"],
            full_name=row.get("full_name"),
        )
        try:
            user = await crud_user.create(db, obj_in=user_in)
            created.append(user)
        except IntegrityError:
            await db.rollback()
            continue  # skip duplicate rows
    return created
