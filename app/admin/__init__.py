"""HTMX Admin Dashboard - auto-discovery of SQLAlchemy models."""

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import Boolean, Integer, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import require_admin
from app.api.deps import get_db, get_read_db
from app.core.cache import cache as redis_cache
from app.core.jwt_blacklist import (
    get_session,
    list_active_sessions,
    revoke_session,
)
from app.decorators.rate_limit import rate_limit
from app.identity.auth.permissions import has_permission
from app.identity.crud.user import user as crud_user
from app.identity.models import Permission, Role, User
from app.identity.models.api_key import ApiKey
from app.identity.models.tenant import Tenant
from app.models.audit_log import AuditLog
from app.models.base import BaseModel, SoftDeleteMixin
from app.models.file import File
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference

logger = logging.getLogger("app.admin")

# ---------- Registry ----------
_registry: dict[str, dict[str, Any]] = {}

_custom_crud: dict[str, Any] = {
    "User": crud_user,
}


def register_admin(model: type[BaseModel], **options: Any) -> None:
    """Register a SQLAlchemy model for the admin panel."""
    table_name = model.__tablename__
    columns = [
        c.key for c in inspect(model).columns if c.key not in ("id", "created_at", "updated_at")
    ]
    _registry[table_name] = {
        "model": model,
        "columns": options.get("columns", columns),
        "search_columns": options.get("search_columns", columns[:2]),
        "form_fields": options.get("form_fields", columns),
        "list_display": options.get("list_display", columns[:4]),
        "permission": options.get("permission", f"{table_name}:admin"),
    }


# Auto-register known models
register_admin(
    User,
    list_display=["email", "username", "is_active", "is_verified"],
    search_columns=["email", "username"],
    form_fields=["email", "username", "password", "full_name", "is_active", "is_verified"],
    permission="user:admin",
)
register_admin(
    Role,
    list_display=["name", "description"],
    search_columns=["name"],
    form_fields=["name", "description"],
    permission="role:admin",
)
register_admin(
    Permission,
    list_display=["name", "description"],
    search_columns=["name"],
    form_fields=["name", "description"],
    permission="permission:admin",
)
register_admin(
    Tenant,
    list_display=["name", "slug", "is_active"],
    search_columns=["name"],
    form_fields=["name", "slug", "is_active"],
    permission="tenant:admin",
)
register_admin(
    AuditLog,
    list_display=["table_name", "record_id", "action", "actor_id", "created_at"],
    search_columns=["table_name", "action"],
    form_fields=[],
    permission="audit:admin",
)
register_admin(
    ApiKey,
    list_display=["name", "key_prefix", "user_id", "is_active", "created_at"],
    search_columns=["name", "key_prefix"],
    form_fields=["name", "user_id", "is_active", "scopes", "expires_at"],
    permission="api_key:admin",
)
register_admin(
    NotificationPreference,
    list_display=["user_id", "email_enabled", "in_app_enabled", "webhook_enabled"],
    search_columns=["user_id"],
    form_fields=["user_id", "email_enabled", "in_app_enabled", "webhook_enabled"],
    permission="notification:admin",
)
register_admin(
    Notification,
    list_display=["user_id", "event_type", "title", "is_read", "created_at"],
    search_columns=["event_type", "title"],
    form_fields=["user_id", "event_type", "title", "body", "is_read"],
    permission="notification:admin",
)
register_admin(
    File,
    list_display=["original_filename", "mime_type", "size_bytes", "uploader_id", "created_at"],
    search_columns=["original_filename", "mime_type"],
    form_fields=[],
    permission="file:admin",
)

# ---------- Templates ----------
TEMPLATES_DIR = Path(__file__).parent / "templates"
_auto_reload = os.environ.get("ENVIRONMENT", "production") == "development"
env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    auto_reload=_auto_reload,
)


def render(template_name: str, **kwargs: Any) -> str:
    template = env.get_template(template_name)
    return template.render(**kwargs)


# ---------- Helpers ----------
def _coerce_value(model: type[BaseModel], field: str, value: str) -> Any:
    """Cast a string form value to the appropriate Python type."""
    column = inspect(model).columns.get(field)
    if column is None:
        return value
    col_type = type(column.type)
    if col_type is Boolean:
        return value.lower() in ("1", "true", "on")
    if col_type is Integer:
        return int(value)
    return value


def _set_default_password_for_user(obj: User) -> None:
    """Validate that a password was provided for new User objects."""
    if isinstance(obj, User) and not obj.hashed_password:
        raise HTTPException(status_code=400, detail="Password is required when creating a user")


# ---------- Router ----------
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_admin)) -> Any:
    """Admin home page with model index."""
    models_info = []
    for table_name, config in _registry.items():
        if has_permission(user, [config["permission"]]):
            models_info.append(
                {
                    "name": table_name,
                    "label": config["model"].__name__,
                    "permission": config["permission"],
                }
            )
    models_info.append(
        {
            "name": "sessions",
            "label": "Sessions",
            "permission": "user:admin",
        }
    )
    return render("dashboard.html", user=user, models=models_info, request=request)


@router.get("/{table_name}", response_class=HTMLResponse)
async def admin_list(
    request: Request,
    table_name: str,
    db: AsyncSession = Depends(get_read_db),
    user: User = Depends(require_admin),
    search: str = "",
    page: int = 1,
) -> Any:
    """List records for a model."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    model = config["model"]
    from sqlalchemy import func, or_

    query = select(model)
    if search:
        filters = [
            getattr(model, col).ilike(f"%{search}%")
            for col in config["search_columns"]
            if hasattr(model, col)
        ]
        if filters:
            query = query.where(or_(*filters)) if len(filters) > 1 else query.where(filters[0])

    # Pagination — use cached count when no search filter is active
    per_page = 20
    if not search:
        cache_key = f"admin_count:{table_name}"
        cached_total = await redis_cache.get(cache_key)
        if cached_total is not None:
            total = int(cached_total)
        else:
            count_query = select(func.count()).select_from(query.subquery())
            total = (await db.scalar(count_query)) or 0
            await redis_cache.set(cache_key, total, ttl=60)
    else:
        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.scalar(count_query)) or 0
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rows = result.scalars().all()

    return render(
        "list.html",
        user=user,
        table_name=table_name,
        model_name=config["model"].__name__,
        rows=rows,
        columns=config["list_display"],
        search=search,
        page=page,
        total=total,
        per_page=per_page,
    )


@router.get("/{table_name}/{id}", response_class=HTMLResponse)
async def admin_detail(
    request: Request,
    table_name: str,
    id: int,
    db: AsyncSession = Depends(get_read_db),
    user: User = Depends(require_admin),
) -> Any:
    """View a single record."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    obj = await db.get(config["model"], id)
    if not obj:
        raise HTTPException(status_code=404)
    return render(
        "detail.html",
        user=user,
        obj=obj,
        columns=config["columns"],
        table_name=table_name,
    )


@router.get("/{table_name}/{id}/edit", response_class=HTMLResponse)
async def admin_edit_form(
    request: Request,
    table_name: str,
    id: int,
    db: AsyncSession = Depends(get_read_db),
    user: User = Depends(require_admin),
) -> Any:
    """Edit form for a record."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    obj = await db.get(config["model"], id)
    if not obj:
        raise HTTPException(status_code=404)
    return render(
        "form.html",
        user=user,
        obj=obj,
        fields=config["form_fields"],
        table_name=table_name,
        editing=True,
    )


@router.post("/{table_name}/{id}/edit")
@rate_limit(times=30, seconds=60)  # type: ignore[untyped-decorator]
async def admin_edit(
    request: Request,
    table_name: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> Any:
    """Process edit form submission."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    obj = await db.get(config["model"], id)
    if not obj:
        raise HTTPException(status_code=404)

    form_data = await request.form()
    # Duplicate check for User model
    if config["model"] is User and "email" in form_data:
        existing = await db.execute(select(User).where(User.email == str(form_data["email"])))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already exists")

    for field in config["form_fields"]:
        if field in form_data:
            value = _coerce_value(config["model"], field, str(form_data[field]))
            setattr(obj, field, value)
    _set_default_password_for_user(obj)
    await db.commit()
    await redis_cache.delete(f"admin_count:{table_name}")
    return RedirectResponse(url=f"/admin/{table_name}", status_code=303)


@router.get("/{table_name}/create", response_class=HTMLResponse)
async def admin_create_form(
    request: Request, table_name: str, user: User = Depends(require_admin)
) -> Any:
    """Create form for a new record."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    return render(
        "form.html",
        user=user,
        obj=None,
        fields=config["form_fields"],
        table_name=table_name,
        editing=False,
    )


@router.post("/{table_name}/create")
@rate_limit(times=30, seconds=60)  # type: ignore[untyped-decorator]
async def admin_create(
    request: Request,
    table_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> Any:
    """Process create form submission."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    form_data = await request.form()
    # Duplicate check for User model
    if config["model"] is User and "email" in form_data:
        existing = await db.execute(select(User).where(User.email == str(form_data["email"])))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already exists")

    model = config["model"]
    obj = model()
    for field in config["form_fields"]:
        if field in form_data:
            value = _coerce_value(model, field, str(form_data[field]))
            setattr(obj, field, value)
    _set_default_password_for_user(obj)
    db.add(obj)
    await db.commit()
    await redis_cache.delete(f"admin_count:{table_name}")
    return RedirectResponse(url=f"/admin/{table_name}", status_code=303)


@router.post("/{table_name}/{id}/delete")
@rate_limit(times=30, seconds=60)  # type: ignore[untyped-decorator]
async def admin_delete(
    request: Request,
    table_name: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> Any:
    """Delete a record."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    obj = await db.get(config["model"], id)
    if obj:
        if issubclass(config["model"], SoftDeleteMixin):
            obj.deleted_at = datetime.now(UTC)
            db.add(obj)
            await db.commit()
        else:
            await db.delete(obj)
            await db.commit()
    await redis_cache.delete(f"admin_count:{table_name}")
    return RedirectResponse(url=f"/admin/{table_name}", status_code=303)


@router.post("/{table_name}/{id}/restore")
@rate_limit(times=30, seconds=60)  # type: ignore[untyped-decorator]
async def admin_restore(
    request: Request,
    table_name: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> Any:
    """Restore a soft-deleted record."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not issubclass(config["model"], SoftDeleteMixin):
        raise HTTPException(status_code=400, detail="Model does not support soft-delete")
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    obj = await db.get(config["model"], id)
    if obj and obj.deleted_at is not None:
        obj.deleted_at = None
        db.add(obj)
        await db.commit()
    await redis_cache.delete(f"admin_count:{table_name}")
    return RedirectResponse(url=f"/admin/{table_name}", status_code=303)


@router.get("/{table_name}/trashed", response_class=HTMLResponse)
async def admin_list_trashed(
    request: Request,
    table_name: str,
    q: str = "",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> HTMLResponse:
    """List soft-deleted records for a model."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not issubclass(config["model"], SoftDeleteMixin):
        raise HTTPException(status_code=400, detail="Model does not support soft-delete")
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    model = config["model"]
    page_size = 20
    offset = (page - 1) * page_size

    stmt = (
        select(model)
        .where(model.deleted_at.isnot(None))
        .order_by(model.deleted_at.desc())
        .offset(offset)
        .limit(page_size + 1)
    )
    if q and hasattr(model, config["search_columns"][0] if config["search_columns"] else ""):
        col = getattr(model, config["search_columns"][0], None)
        if col is not None:
            stmt = stmt.where(col.ilike(f"%{q}%"))

    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    has_next = len(rows) > page_size
    items = rows[:page_size]

    template = env.get_template("list.html")
    html = template.render(
        table_name=table_name,
        items=items,
        columns=config["list_display"],
        q=q,
        page=page,
        has_next=has_next,
        user=user,
        trashed_view=True,
    )
    return HTMLResponse(content=html)


# ---------- Session management (Redis-based) ----------


@router.get("/sessions", response_class=HTMLResponse)
async def admin_list_sessions(
    request: Request,
    db: AsyncSession = Depends(get_read_db),
    user: User = Depends(require_admin),
    user_id: int | None = None,
) -> Any:
    """List active sessions for a user (or prompt to select)."""
    sessions: list[dict[str, str]] = []
    selected_user = None
    if user_id:
        selected_user = await crud_user.get(db, id=user_id)
        if selected_user:
            sessions = await list_active_sessions(user_id)
    return render(
        "sessions.html",
        user=user,
        selected_user=selected_user,
        sessions=sessions,
        request=request,
    )


@router.post("/sessions/revoke", response_class=HTMLResponse)
async def admin_revoke_session(
    request: Request,
    admin_user: User = Depends(require_admin),
) -> Any:
    """Revoke a specific session by JTI."""
    form = await request.form()
    jti = str(form.get("jti", ""))
    user_id = int(str(form.get("user_id", 0)))
    if not jti or not user_id:
        raise HTTPException(status_code=400, detail="jti and user_id required")
    session_data = await get_session(user_id, jti)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    exp = int(session_data.get("expires_at", 0))
    await revoke_session(user_id, jti, exp)
    return RedirectResponse(url=f"/admin/sessions?user_id={user_id}", status_code=303)
