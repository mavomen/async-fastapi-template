"""Metrics endpoint for Prometheus scraping."""

from fastapi import APIRouter, Response
from prometheus_client import generate_latest, REGISTRY

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    """Expose Prometheus metrics."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain; version=0.0.4",
    )
