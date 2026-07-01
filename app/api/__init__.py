"""API package."""

from fastapi import APIRouter

from app.api.endpoints import (
    api_keys,
    auth,
    csp,
    events,
    files,
    tasks,
    tenant_ip_rules,
    tenants,
    users,
)

api_router = APIRouter()

api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(api_keys.router, prefix="/auth", tags=["auth"])
api_router.include_router(csp.router, prefix="", tags=["security"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(tenant_ip_rules.router, tags=["ip-rules"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
