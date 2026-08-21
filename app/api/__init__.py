"""API package.

Composition root for the v1 API. Domain routers are imported from their
bounded contexts (app.identity.api.endpoints, app.notifications...);
prefixes/tags/order here define the public HTTP surface — keep stable.
"""

from fastapi import APIRouter

from app.api.endpoints import cms, csp, events, files, tasks
from app.identity.api.endpoints import api_keys, auth, tenant_ip_rules, tenants, totp, users
from app.notifications.api.endpoints import notifications, webhooks

api_router = APIRouter()

api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(api_keys.router, prefix="/auth", tags=["auth"])
api_router.include_router(totp.router, prefix="/auth", tags=["auth"])
api_router.include_router(csp.router, prefix="", tags=["security"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(tenant_ip_rules.router, tags=["ip-rules"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(cms.router, prefix="/cms", tags=["cms"])
