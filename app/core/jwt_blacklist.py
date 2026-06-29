"""
Redis-backed JWT blacklist for token revocation.

Tokens are identified by their `jti` (JWT ID) claim and stored in a Redis SET
per user under `jwt:blacklist:{user_id}`. Each member is `{jti}:{exp}` and
expired entries are pruned on read.
"""

from datetime import UTC, datetime

import structlog

from app.core.cache import cache
from app.core.config import settings

logger = structlog.get_logger("app.jwt_blacklist")

_BLACKLIST_PREFIX = "jwt:blacklist"
_REVOKED_ALL_PREFIX = "jwt:revoked-all"


def _user_key(user_id: int) -> str:
    return f"{_BLACKLIST_PREFIX}:{user_id}"


def _revoked_all_key(user_id: int) -> str:
    return f"{_REVOKED_ALL_PREFIX}:{user_id}"


async def blacklist_token(user_id: int, jti: str, exp: int) -> None:
    if not settings.JWT_BLACKLIST_ENABLED:
        return
    ttl = min(settings.JWT_BLACKLIST_TTL, max(1, exp - int(datetime.now(UTC).timestamp())))
    key = _user_key(user_id)
    member = f"{jti}:{exp}"
    r = cache.get_redis()
    await r.sadd(key, member)  # type: ignore[misc]
    await r.expire(key, ttl)
    logger.debug("token_blacklisted", user_id=user_id, jti=jti)


async def is_token_blacklisted(user_id: int, jti: str) -> bool:
    if not settings.JWT_BLACKLIST_ENABLED:
        return False
    key = _user_key(user_id)
    now = int(datetime.now(UTC).timestamp())
    r = cache.get_redis()
    members: set[str] = await r.smembers(key)  # type: ignore[misc]
    for member in members:
        parts = member.split(":", 1)
        if len(parts) == 2:
            stored_jti, stored_exp = parts
            if int(stored_exp) < now:
                continue
            if stored_jti == jti:
                return True
    return False


async def revoke_all_user_tokens(user_id: int) -> int:
    if not settings.JWT_BLACKLIST_ENABLED:
        return 0
    key = _user_key(user_id)
    r = cache.get_redis()
    member_count: int = await r.scard(key)  # type: ignore[misc]
    await r.delete(key)
    revoked_key = _revoked_all_key(user_id)
    await r.setex(revoked_key, settings.JWT_BLACKLIST_TTL, str(int(datetime.now(UTC).timestamp())))
    logger.debug("all_tokens_revoked", user_id=user_id, member_count=member_count)
    return member_count


async def get_blacklisted_at(user_id: int) -> int | None:
    revoked_key = _revoked_all_key(user_id)
    r = cache.get_redis()
    val: str | None = await r.get(revoked_key)
    if val is not None:
        return int(val)
    return None
