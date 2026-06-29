"""API package."""

from fastapi import APIRouter

from app.api.endpoints import auth, csp, events, files, tasks, tenants, users

api_router = APIRouter()

api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(csp.router, prefix="", tags=["security"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
