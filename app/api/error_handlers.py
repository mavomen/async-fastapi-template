"""Global exception handlers for FastAPI."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def configure_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> ORJSONResponse:
        return ORJSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_code": exc.error_code},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> ORJSONResponse:
        return ORJSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_code": "HTTP_ERROR"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> ORJSONResponse:
        """Reformat validation errors to a user-friendly structure."""
        errors = exc.errors()
        simplified: list[dict[str, Any]] = []
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
                "error_code": "VALIDATION_ERROR",
                "errors": simplified,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
        """Catch-all for unhandled exceptions, logs and returns 500."""
        logger.exception("Unhandled exception: %s", exc)
        return ORJSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"},
        )
