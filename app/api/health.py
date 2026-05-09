"""Health check endpoints with dependency checks."""

from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(tags=["health"])


async def _check_database(db: AsyncSession) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception:
        return {"database": "disconnected"}


async def _check_redis() -> dict:
    try:
        from app.core.cache import cache

        if cache._redis:
            await cache._redis.ping()  # type: ignore[misc]
        else:
            r = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
            await r.ping()  # type: ignore[misc]
            await r.close()
        return {"redis": "connected"}
    except Exception:
        return {"redis": "disconnected"}


@router.get(
    "/",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def health_check() -> dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


@router.get(
    "/ready",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def readiness_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Readiness check including database and Redis status."""
    db_status = await _check_database(db)
    redis_status = await _check_redis()

    all_connected = all(v == "connected" for v in [db_status["database"], redis_status["redis"]])

    return {
        "status": "ready" if all_connected else "degraded",
        **db_status,
        **redis_status,
    }


@router.get(
    "/live",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def liveness_check() -> dict[str, Any]:
    """Liveness check endpoint (for k8s liveness probes)."""
    return {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


@router.get(
    "/dependencies",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def dependencies_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Detailed dependency health check."""
    db_status = await _check_database(db)
    redis_status = await _check_redis()

    return {
        "status": "ok",
        "components": {
            "database": db_status["database"],
            "redis": redis_status["redis"],
        },
    }
