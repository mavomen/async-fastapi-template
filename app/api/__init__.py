"""API package."""

from fastapi import APIRouter

from app.api.endpoints import auth
from app.api.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
