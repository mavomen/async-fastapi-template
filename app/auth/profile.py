"""User profile page with HTMX-driven updates and avatar upload."""

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.crud.user import user as crud_user
from app.models.user import User
from app.schemas.user import UserUpdate

router = APIRouter()

TEMPLATES_DIR = Path(__file__).parent.parent / "admin" / "templates"
_auto_reload = os.environ.get("ENVIRONMENT", "production") == "development"
env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    auto_reload=_auto_reload,
)


@router.get("/", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Render the user profile page."""
    template = env.get_template("profile.html")
    return template.render(user=current_user, request=request)


@router.post("/edit", response_class=HTMLResponse)
async def profile_edit(
    request: Request,
    full_name: str = Form(None),
    email: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Inline edit for profile fields (HTMX)."""
    update_data = {}
    if full_name is not None:
        update_data["full_name"] = full_name
    if email is not None:
        update_data["email"] = email
    if update_data:
        user_update = UserUpdate(**update_data)
        await crud_user.update(db, db_obj=current_user, obj_in=user_update)
    return Response(status_code=200, content="Saved", media_type="text/plain")


@router.post("/avatar", response_class=HTMLResponse)
async def profile_avatar(
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Upload a profile avatar (placeholder)."""
    return HTMLResponse(
        content='<img src="/static/default-avatar.png" class="w-24 h-24 rounded-full" />',
        status_code=200,
    )
