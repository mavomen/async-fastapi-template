"""Health check endpoints."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
router = APIRouter(tags=["health"])


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
    """Readiness check endpoint (for k8s readiness probes)."""
    # Check database connectivity
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "ready",
        "database": db_status,
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
