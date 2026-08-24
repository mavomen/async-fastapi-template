"""Usage metering: Redis-backed counters for billable dimensions.

Counters are period-scoped (key includes the subscription period start)
and expire shortly after the period ends. Durability trade-off is
deliberate: counters are best-effort. On any Redis failure we fail open
(log and allow) — an infrastructure outage must never take the API down,
and the resulting under-count is the customer-friendly billing error.

Overage-only invoicing: ``billable = max(0, used - included_quantity)``.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.cache import cache

logger = logging.getLogger("app.billing.usage")

#: Grace period (seconds) a counter survives past period end so late
#: requests in flight still land on the right bucket.
COUNTER_TTL_GRACE_SECONDS = 3600

DEFAULT_DIMENSION = "api_requests"


def counter_key(tenant_id: int, dimension: str, period_start: datetime) -> str:
    return f"billing:usage:{tenant_id}:{dimension}:{int(period_start.timestamp())}"


def ttl_for(period_end: datetime, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    return max(60, int((period_end - now).total_seconds()) + COUNTER_TTL_GRACE_SECONDS)


async def increment(
    tenant_id: int,
    dimension: str,
    period_start: datetime,
    period_end: datetime,
    amount: int = 1,
) -> int | None:
    """Add ``amount`` to the tenant's counter; returns new value or None on failure."""
    try:
        redis = cache.get_redis()
        key = counter_key(tenant_id, dimension, period_start)
        pipe = redis.pipeline()
        pipe.incrby(key, amount)
        pipe.expire(key, ttl_for(period_end))
        results = await pipe.execute()
        return int(results[0])
    except Exception:
        logger.exception(
            "usage increment failed (fail-open): tenant=%s dim=%s", tenant_id, dimension
        )
        return None


async def get_usage(tenant_id: int, dimension: str, period_start: datetime) -> int:
    """Current counter value; 0 when missing or on Redis failure."""
    try:
        redis = cache.get_redis()
        value = await redis.get(counter_key(tenant_id, dimension, period_start))
        return int(value) if value is not None else 0
    except Exception:
        logger.exception("usage read failed (fail-open): tenant=%s dim=%s", tenant_id, dimension)
        return 0


def compute_overage(used: int, included_quantity: int, unit_amount_cents: int) -> int:
    """Billable cents for one dimension (overage-only)."""
    billable_units = max(0, used - included_quantity)
    return billable_units * unit_amount_cents


def extract_metering(plan_metering: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    """Normalize a plan's raw metering JSON into {dimension: config} dicts."""
    if not plan_metering:
        return {}
    out: dict[str, dict[str, int]] = {}
    for name, cfg in plan_metering.items():
        if isinstance(cfg, dict):
            try:
                out[str(name)] = {
                    "unit_amount_cents": int(cfg.get("unit_amount_cents", 0)),
                    "included_quantity": int(cfg.get("included_quantity", 0)),
                }
            except (TypeError, ValueError):
                logger.warning("malformed metering config for %s; skipping", name)
    return out
