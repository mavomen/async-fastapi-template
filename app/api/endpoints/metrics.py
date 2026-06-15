"""Metrics endpoint for Prometheus scraping."""

from fastapi import APIRouter, Response
from prometheus_client import REGISTRY, generate_latest

router = APIRouter()


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Expose application metrics in Prometheus text format for scraping.",
    responses={
        200: {
            "description": "Metrics in Prometheus exposition format",
            "content": {"text/plain; version=0.0.4": {}},
        },
    },
)
async def get_metrics() -> Response:
    """Expose Prometheus metrics."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain; version=0.0.4",
    )
