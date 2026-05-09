"""Simple feature flag system backed by Redis and env vars."""

import os

from app.core.cache import cache

FEATURE_FLAGS = {
    "webauthn": True,
    "graphql_subscriptions": True,
    "admin_dashboard": True,
    "multi_tenancy": True,
    "full_text_search": True,
    "audit_logging": True,
}


async def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled (env > cache > code defaults)."""
    # 1. Env var override
    env_key = f"FEATURE_{feature.upper()}"
    if env_key in os.environ:
        return os.environ[env_key].lower() in ("1", "true", "yes")

    if feature not in FEATURE_FLAGS:
        return False

    # 2. Cache
    cached = await cache.get(f"feature:{feature}")
    if cached is not None:
        return bool(cached)

    # 3. Default
    return FEATURE_FLAGS[feature]
