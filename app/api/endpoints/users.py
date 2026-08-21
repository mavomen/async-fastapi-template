"""User management endpoints with RBAC protection and data export."""

import asyncio
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_read_db
from app.auth.permissions import PermissionChecker
from app.core.security import get_password_hash
from app.crud.user import user as crud_user
from app.models.user import User
from app.schemas.user import PurgeResponse, UserCreate, UserDetailResponse, UserUpdate
from app.utils.export_csv import export_to_csv
from app.utils.export_excel import export_to_excel
from app.utils.pagination import CursorPage, CursorParams, decode_cursor

router = APIRouter()


@router.get(
    "/",
    summary="List all users",
    description="Retrieve a paginated list of all users. Supports cursor-based pagination. "
    "Requires `user:read` permission.",
    responses={
        200: {"description": "List of users with roles"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
    },
)
async def list_users(
    cursor: str | None = Query(None, description="Cursor from previous page response"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(PermissionChecker(["user:read"])),
) -> Any:
    """List all users with cursor-based pagination (requires 'user:read' permission)."""
    cursor_id = decode_cursor(cursor) if cursor else None
    users, next_cursor = await crud_user.get_multi_cursor(db, cursor=cursor_id, limit=size)
    return CursorPage.create(users, CursorParams(cursor=cursor, size=size))


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
    """Delete (soft-delete) a user (requires 'user:delete' permission)."""
    user = await crud_user.delete(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "User deleted successfully"}


@router.post(
    "/{user_id}/restore",
    response_model=UserDetailResponse,
    summary="Restore a deleted user",
    description="Restore a soft-deleted user. Requires `user:delete` permission.",
    responses={
        200: {"description": "User restored"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not enough permissions"},
        404: {"description": "Deleted user not found"},
    },
)
async def restore_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["user:delete"])),
) -> Any:
    """Restore a soft-deleted user (requires 'user:delete' permission)."""
    user = await crud_user.restore(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Deleted user not found")
    return await crud_user.get_with_roles(db, id=user.id)


@router.get(
    "/trashed",
    response_model=list[UserDetailResponse],
    summary="List deleted users",
    description="List soft-deleted users. Requires `user:read` permission.",
)
async def list_trashed_users(
    cursor: str | None = Query(None, description="Cursor from previous page response"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(PermissionChecker(["user:read"])),
) -> Any:
    """List soft-deleted users (requires 'user:read' permission)."""
    cursor_id = decode_cursor(cursor) if cursor else None
    users, next_cursor = await crud_user.get_multi_cursor(
        db, cursor=cursor_id, limit=size, include_deleted=True
    )
    return CursorPage.create(users, CursorParams(cursor=cursor, size=size))


@router.post(
    "/purge",
    response_model=PurgeResponse,
    summary="Purge old deleted users",
    description="Hard-delete users that have been soft-deleted for more than N days. "
    "Requires superuser permissions.",
)
async def purge_deleted_users(
    older_than_days: int = Query(90, ge=1, description="Minimum age in days"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["user:delete"])),
) -> Any:
    """Hard-delete users soft-deleted more than N days ago (superuser only)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser required")
    count = await crud_user.purge(db, older_than_days=older_than_days)
    return PurgeResponse(purged_count=count)


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
    """Create multiple users in a single transaction (requires user:write)."""
    return await crud_user.bulk_create(db, objs_in=users)


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
    """Bulk-import users from a CSV file in a single commit (requires user:write).

    Duplicate emails are skipped via a pre-query check.
    Passwords are hashed off the event loop.
    """
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode()))
    raw_rows = [
        {
            "email": r["email"],
            "username": r["username"],
            "password": r["password"],
            "full_name": r.get("full_name"),
        }
        for r in reader
    ]
    if not raw_rows:
        return []

    existing = await db.execute(
        select(User.email).where(User.email.in_([r["email"] for r in raw_rows]))
    )
    existing_emails: set[str] = {row[0] for row in existing.all()}

    async def _prepare(row: dict[str, Any]) -> User | None:
        if row["email"] in existing_emails:
            return None
        hashed = await asyncio.to_thread(get_password_hash, row["password"])
        return User(
            email=row["email"],
            username=row["username"],
            hashed_password=hashed,
            full_name=row.get("full_name"),
        )

    orm_objs = [
        obj for obj in (await asyncio.gather(*[_prepare(r) for r in raw_rows])) if obj is not None
    ]
    if not orm_objs:
        return []

    db.add_all(orm_objs)
    await db.commit()
    for obj in orm_objs:
        await db.refresh(obj)
    return orm_objs
