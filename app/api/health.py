"""Health check endpoints with dependency checks."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_read_db

router = APIRouter(tags=["health"])


async def _check_database(db: AsyncSession) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception:
        return {"database": "disconnected"}


async def _check_redis() -> dict[str, str]:
    try:
        from app.core.cache import cache

        ok = await cache.ping()
        return {"redis": "connected" if ok else "disconnected"}
    except Exception:
        return {"redis": "disconnected"}


async def _check_event_bus() -> dict[str, str]:
    """Check event bus connectivity (Redis or Kafka)."""
    if settings.EVENT_BUS_BACKEND == "redis":
        try:
            from app.core.cache import cache

            ok = await cache.ping()
            return {"event_bus": "connected" if ok else "disconnected"}
        except Exception:
            return {"event_bus": "disconnected"}
    elif settings.EVENT_BUS_BACKEND == "kafka":
        try:
            from kafka import KafkaProducer

            producer = KafkaProducer(
                bootstrap_servers=settings.EVENT_BUS_KAFKA_SERVERS,
                request_timeout_ms=2000,
            )
            producer.close(timeout=3)
            return {"event_bus": "connected"}
        except Exception:
            return {"event_bus": "disconnected"}
    return {"event_bus": "unknown"}


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
async def readiness_check(db: AsyncSession = Depends(get_read_db)) -> dict[str, Any]:
    """Readiness check including database, Redis, and event bus status."""
    db_status = await _check_database(db)
    redis_status = await _check_redis()
    event_bus_status = await _check_event_bus()

    all_connected = all(
        v == "connected"
        for v in [db_status["database"], redis_status["redis"], event_bus_status["event_bus"]]
    )

    return {
        "status": "ready" if all_connected else "degraded",
        **db_status,
        **redis_status,
        **event_bus_status,
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
async def dependencies_check(db: AsyncSession = Depends(get_read_db)) -> dict[str, Any]:
    """Detailed dependency health check."""
    db_status = await _check_database(db)
    redis_status = await _check_redis()
    event_bus_status = await _check_event_bus()

    return {
        "status": "ok",
        "components": {
            "database": db_status["database"],
            "redis": redis_status["redis"],
            "event_bus": event_bus_status["event_bus"],
        },
    }
