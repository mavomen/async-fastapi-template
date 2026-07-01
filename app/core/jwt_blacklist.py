"""
Redis-backed JWT blacklist for token revocation.

Tokens are identified by their `jti` (JWT ID) claim and stored in a Redis SET
per user under `jwt:blacklist:{user_id}`. Each member is `{jti}:{exp}` and
expired entries are pruned on read.
"""

from datetime import UTC, datetime
from typing import TypedDict

import structlog

from app.core.cache import cache
from app.core.config import settings

logger = structlog.get_logger("app.jwt_blacklist")


class SessionInfo(TypedDict):
    jti: str
    token_type: str
    ip: str
    user_agent: str
    created_at: str
    expires_at: str
    user_id: str


class SessionCreatePayload(TypedDict):
    jti: str
    token_type: str
    ip: str | None
    user_agent: str | None
    iat: int
    exp: int


_BLACKLIST_PREFIX = "jwt:blacklist"
_REVOKED_ALL_PREFIX = "jwt:revoked-all"
_SESSION_PREFIX = "user:sessions"
_SESSION_META_PREFIX = "user:session:meta"


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


def _sessions_key(user_id: int) -> str:
    return f"{_SESSION_PREFIX}:{user_id}"


def _session_meta_key(user_id: int, jti: str) -> str:
    return f"{_SESSION_META_PREFIX}:{user_id}:{jti}"


async def store_session(
    user_id: int,
    payload: SessionCreatePayload,
) -> None:
    if not settings.JWT_BLACKLIST_ENABLED:
        return
    ttl = min(
        settings.JWT_BLACKLIST_TTL,
        max(1, payload["exp"] - int(datetime.now(UTC).timestamp())),
    )
    skey = _sessions_key(user_id)
    mkey = _session_meta_key(user_id, payload["jti"])
    r = cache.get_redis()
    await r.zadd(skey, {payload["jti"]: payload["iat"]})
    await r.expire(skey, ttl)
    await r.hset(
        mkey,
        mapping={
            "jti": payload["jti"],
            "token_type": payload["token_type"],
            "ip": payload["ip"] or "",
            "user_agent": payload["user_agent"] or "",
            "created_at": str(payload["iat"]),
            "expires_at": str(payload["exp"]),
            "user_id": str(user_id),
        },
    )  # type: ignore[misc]
    await r.expire(mkey, ttl)
    logger.debug(
        "session_stored", user_id=user_id, jti=payload["jti"], token_type=payload["token_type"]
    )


async def list_active_sessions(user_id: int) -> list[dict[str, str]]:
    if not settings.JWT_BLACKLIST_ENABLED:
        return []
    skey = _sessions_key(user_id)
    r = cache.get_redis()
    members: list[str] = await r.zrevrange(skey, 0, -1)
    now = int(datetime.now(UTC).timestamp())
    sessions: list[dict[str, str]] = []
    for jti in members:
        mkey = _session_meta_key(user_id, jti)
        meta: dict[str, str] = await r.hgetall(mkey)  # type: ignore[misc]
        if not meta or "jti" not in meta:
            continue
        exp = int(meta.get("expires_at", 0))
        if exp < now:
            await r.zrem(skey, jti)
            await r.delete(mkey)
            continue
        sessions.append(meta)
    return sessions


async def get_session(user_id: int, jti: str) -> dict[str, str] | None:
    mkey = _session_meta_key(user_id, jti)
    r = cache.get_redis()
    meta: dict[str, str] = await r.hgetall(mkey)  # type: ignore[misc]
    if not meta or "jti" not in meta:
        return None
    return meta


async def revoke_session(user_id: int, jti: str, exp: int) -> None:
    if not settings.JWT_BLACKLIST_ENABLED:
        return
    skey = _sessions_key(user_id)
    mkey = _session_meta_key(user_id, jti)
    r = cache.get_redis()
    await r.zrem(skey, jti)
    await r.delete(mkey)
    await blacklist_token(user_id, jti, exp)
    logger.debug("session_revoked", user_id=user_id, jti=jti)


async def revoke_all_user_sessions(user_id: int) -> int:
    if not settings.JWT_BLACKLIST_ENABLED:
        return 0
    skey = _sessions_key(user_id)
    r = cache.get_redis()
    members: list[str] = await r.zrevrange(skey, 0, -1)
    count = 0
    now = int(datetime.now(UTC).timestamp())
    for jti in members:
        mkey = _session_meta_key(user_id, jti)
        meta: dict[str, str] = await r.hgetall(mkey)  # type: ignore[misc]
        exp = int(meta.get("expires_at", 0)) if meta else 0
        await blacklist_token(user_id, jti, exp)
        await r.delete(mkey)
        count += 1
    await r.delete(skey)
    revoked_key = _revoked_all_key(user_id)
    await r.setex(revoked_key, settings.JWT_BLACKLIST_TTL, str(now))
    logger.debug("all_sessions_revoked", user_id=user_id, count=count)
    return count
