"""Health check endpoints."""

from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import ORJSONResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def health_check() -> dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "async-fastapi-template",
    }


@router.get(
    "/health/ready",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def readiness_check() -> dict[str, Any]:
    """Readiness check endpoint (for k8s readiness probes)."""
    # TODO: Add database and Redis connectivity checks
    return {
        "status": "ready",
        "checks": {
            "database": "not_implemented",
            "redis": "not_implemented",
        },
    }


@router.get(
    "/health/live",
    response_class=ORJSONResponse,
    status_code=status.HTTP_200_OK,
)
async def liveness_check() -> dict[str, Any]:
    """Liveness check endpoint (for k8s liveness probes)."""
    return {"status": "alive"}
