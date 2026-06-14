"""Global exception handlers for FastAPI."""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def configure_exception_handlers(app):
    """Register all custom exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return ORJSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return ORJSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Reformat validation errors to a user-friendly structure."""
        errors = exc.errors()
        # Simplify the error list
        simplified = []
        for err in errors:
            simplified.append(
                {
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"],
                }
            )
        return ORJSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": simplified,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Catch-all for unhandled exceptions, logs and returns 500."""
        logger.exception("Unhandled exception: %s", exc)
        return ORJSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
