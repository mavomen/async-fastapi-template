"""Simple feature flag system backed by Redis."""

from app.core.cache import cache

FEATURE_FLAGS = {
    "webauthn": True,
    "graphql_subscriptions": True,
    "admin_dashboard": True,
    "multi_tenancy": True,
}


async def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled (cache + hardcoded defaults)."""
    if feature not in FEATURE_FLAGS:
        return False
    # Try cache first
    cached = await cache.get(f"feature:{feature}")
    if cached is not None:
        return cached
    return FEATURE_FLAGS[feature]
