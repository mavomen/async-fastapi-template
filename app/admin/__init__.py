"""HTMX Admin Dashboard - auto-discovery of SQLAlchemy models."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import Boolean, Integer, inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import require_admin
from app.api.deps import get_db
from app.auth.permissions import has_permission
from app.core.security import get_password_hash
from app.crud.user import user as crud_user
from app.models import Permission, Role, User
from app.models.base import BaseModel
from app.models.tenant import Tenant

# ---------- Registry ----------
_registry: dict[str, dict[str, Any]] = {}

_custom_crud: dict[str, Any] = {
    "User": crud_user,
}


def register_admin(model: type[BaseModel], **options) -> None:
    """Register a SQLAlchemy model for the admin panel."""
    table_name = model.__tablename__
    columns = [
        c.key
        for c in inspect(model).columns
        if c.key not in ("id", "created_at", "updated_at")
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
    form_fields=["email", "username", "full_name", "is_active", "is_verified"],
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

# ---------- Templates ----------
TEMPLATES_DIR = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def render(template_name: str, **kwargs) -> str:
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
    """Assign a default hashed password if this is a User without one."""
    if isinstance(obj, User) and not obj.hashed_password:
        obj.hashed_password = get_password_hash("Admin123!")  # placeholder


# ---------- Router ----------
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_admin)):
    """Admin home page with model index."""
    models_info = []
    for table_name, config in _registry.items():
        if has_permission(user, [config["permission"]]):
            models_info.append({
                "name": table_name,
                "label": config["model"].__name__,
                "permission": config["permission"],
            })
    return render("dashboard.html", user=user, models=models_info, request=request)


@router.get("/{table_name}", response_class=HTMLResponse)
async def admin_list(
    request: Request,
    table_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
    search: str = "",
    page: int = 1,
):
    """List records for a model."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    model = config["model"]
    from sqlalchemy import func, or_, select

    query = select(model)
    if search:
        filters = [
            getattr(model, col).ilike(f"%{search}%")
            for col in config["search_columns"]
            if hasattr(model, col)
        ]
        if filters:
            query = query.where(or_(*filters)) if len(filters) > 1 else query.where(filters[0])

    # Pagination
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.scalar(count_query)) or 0
    per_page = 20
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
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
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
        "detail.html", user=user, obj=obj, columns=config["columns"], table_name=table_name
    )


@router.get("/{table_name}/{id}/edit", response_class=HTMLResponse)
async def admin_edit_form(
    request: Request,
    table_name: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
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
async def admin_edit(
    request: Request,
    table_name: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
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
    for field in config["form_fields"]:
        if field in form_data:
            value = _coerce_value(config["model"], field, str(form_data[field]))
            setattr(obj, field, value)
    _set_default_password_for_user(obj)
    await db.commit()
    return RedirectResponse(url=f"/admin/{table_name}", status_code=303)


@router.get("/{table_name}/create", response_class=HTMLResponse)
async def admin_create_form(
    request: Request, table_name: str, user: User = Depends(require_admin)
):
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
async def admin_create(
    request: Request,
    table_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Process create form submission."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    form_data = await request.form()
    model = config["model"]
    obj = model()
    for field in config["form_fields"]:
        if field in form_data:
            value = _coerce_value(model, field, str(form_data[field]))
            setattr(obj, field, value)
    _set_default_password_for_user(obj)
    db.add(obj)
    await db.commit()
    return RedirectResponse(url=f"/admin/{table_name}", status_code=303)


@router.get("/{table_name}/{id}/delete")
async def admin_delete(
    request: Request,
    table_name: str,
    id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete a record (GET confirmation handled by HTMX)."""
    config = _registry.get(table_name)
    if not config:
        raise HTTPException(status_code=404)
    if not has_permission(user, [config["permission"]]):
        raise HTTPException(status_code=403)

    obj = await db.get(config["model"], id)
    if obj:
        await db.delete(obj)
        await db.commit()
    return RedirectResponse(url=f"/admin/{table_name}", status_code=303)
