"""Billing API dependencies: usage quota enforcement.

Mounted as a router-level dependency on the authenticated v1 routers so
every counted request runs after auth/tenant resolution. Anonymous or
public surfaces (auth, plan catalog, webhooks) stay uncounted by design.

Counts each request against the tenant's live subscription
``api_requests`` dimension when the plan meters it; over-quota requests
get 429. Entitlements are cached in-process briefly so the hot path
stays DB-free. Gated behind ``BILLING_QUOTA_ENABLED`` (default off);
fails open on internal errors — see app/billing/services/usage.py.
"""

import logging
import time
from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user_or_api_key, get_db
from app.billing.models.subscription import LIVE_STATUSES, Subscription
from app.billing.services import usage as usage_service
from app.core.config import settings
from app.core.exceptions import RateLimitException
from app.identity.models.user import User

logger = logging.getLogger("app.billing.usage")

ENTITLEMENTS_TTL_SECONDS = 60


class _Entitlements:
    """Per-tenant metering snapshot with short TTL."""

    def __init__(
        self,
        config: dict[str, dict[str, int]] | None,
        period_start: datetime | None,
        period_end: datetime | None,
        expires_at: float,
    ) -> None:
        self.config = config or {}
        self.period_start = period_start
        self.period_end = period_end
        self.expires_at = expires_at

    def fresh(self) -> bool:
        return time.monotonic() < self.expires_at


_entitlements_cache: dict[int, _Entitlements] = {}


def invalidate_entitlements(tenant_id: int | None = None) -> None:
    """Drop cached entitlements (tests, admin overrides)."""
    if tenant_id is None:
        _entitlements_cache.clear()
    else:
        _entitlements_cache.pop(tenant_id, None)


async def resolve_entitlements(db: AsyncSession, tenant_id: int) -> _Entitlements | None:
    """Look up the tenant's live subscription metering config (cached)."""
    cached = _entitlements_cache.get(tenant_id)
    if cached is not None and cached.fresh():
        # Negative lookups are cached as period-less sentinels.
        return cached if cached.period_start is not None else None

    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.tenant_id == tenant_id, Subscription.status.in_(LIVE_STATUSES))
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    sub = (await db.execute(stmt)).scalar_one_or_none()
    if sub is None:
        _entitlements_cache[tenant_id] = _Entitlements(
            None, None, None, time.monotonic() + ENTITLEMENTS_TTL_SECONDS
        )
        return None

    ent = _Entitlements(
        config=usage_service.extract_metering(sub.plan.metering if sub.plan else None),
        period_start=sub.current_period_start,
        period_end=sub.current_period_end,
        expires_at=time.monotonic() + ENTITLEMENTS_TTL_SECONDS,
    )
    _entitlements_cache[tenant_id] = ent
    return ent


async def enforce_api_quota(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_or_api_key),
) -> None:
    """Count one API request and hard-block when the allowance is spent."""
    if not settings.BILLING_QUOTA_ENABLED:
        return
    if current_user is None or current_user.tenant_id is None:
        return

    tenant_id = int(current_user.tenant_id)
    over_quota = False
    try:
        ent = await resolve_entitlements(db, tenant_id)
        cfg = ent.config.get(usage_service.DEFAULT_DIMENSION) if ent else None
        period_end = ent.period_end if ent else None
        if ent is None or cfg is None or ent.period_start is None or period_end is None:
            return

        used = await usage_service.increment(
            tenant_id,
            usage_service.DEFAULT_DIMENSION,
            ent.period_start,
            period_end,
        )
        if used is not None and used > int(cfg["included_quantity"]):
            over_quota = True
            logger.info(
                "quota exceeded: tenant=%s used=%s included=%s",
                tenant_id,
                used,
                cfg["included_quantity"],
            )
    except Exception:
        # Fail open on any internal error; availability first.
        logger.exception("quota check failed (fail-open)")
        return

    if over_quota:
        raise RateLimitException(detail="Plan quota exceeded for this billing period")
