"""API package.

Composition root for the v1 API. Domain routers are imported from their
bounded contexts (app.identity.api.endpoints, app.notifications...);
prefixes/tags/order here define the public HTTP surface — keep stable.
"""

from fastapi import APIRouter, Depends

from app.api.endpoints import cms, csp, events, files, tasks
from app.billing.api.deps import enforce_api_quota
from app.billing.api.endpoints import invoices as billing_invoices
from app.billing.api.endpoints import plans as billing_plans
from app.billing.api.endpoints import stripe as billing_stripe
from app.billing.api.endpoints import subscriptions as billing_subscriptions
from app.identity.api.endpoints import api_keys, auth, tenant_ip_rules, tenants, totp, users
from app.notifications.api.endpoints import notifications, webhooks

#: Authenticated product surfaces subject to plan quota enforcement.
#: Only routers whose handlers already enforce auth qualify — adding the
#: dependency elsewhere would silently turn public endpoints into 401s
#: (an unstaged API break). Public/partially-public surfaces (auth,
#: catalog, webhooks, cms, tasks, events) stay uncounted until they
#: gain consistent authentication.
_QUOTA = [Depends(enforce_api_quota)]

api_router = APIRouter()

api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(api_keys.router, prefix="/auth", tags=["auth"])
api_router.include_router(totp.router, prefix="/auth", tags=["auth"])
api_router.include_router(csp.router, prefix="", tags=["security"])
api_router.include_router(
    users.router, prefix="/users", tags=["users"], dependencies=_QUOTA
)
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(files.router, prefix="/files", tags=["files"], dependencies=_QUOTA)
api_router.include_router(
    tenant_ip_rules.router, tags=["ip-rules"], dependencies=_QUOTA
)
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"], dependencies=_QUOTA
)
api_router.include_router(cms.router, prefix="/cms", tags=["cms"])
api_router.include_router(billing_plans.router, prefix="/billing/plans", tags=["billing"])
api_router.include_router(
    billing_subscriptions.router,
    prefix="/billing/subscriptions",
    tags=["billing"],
    dependencies=_QUOTA,
)
api_router.include_router(billing_stripe.router, prefix="/billing/stripe", tags=["billing"])
api_router.include_router(
    billing_invoices.router, prefix="/billing/invoices", tags=["billing"], dependencies=_QUOTA
)
