"""API v2 router — scaffold for future versioned endpoints.

This package provides the infrastructure for adding v2 endpoints alongside v1.
Mount conditionally in app/main.py via API_V2_ENABLED setting.
"""

from fastapi import APIRouter

api_v2_router = APIRouter()
