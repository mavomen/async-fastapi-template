"""Middleware to add security headers to every response."""

from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings


def _build_csp() -> str:
    directives = [
        f"default-src {settings.CSP_DEFAULT_SRC}",
        f"script-src {settings.CSP_SCRIPT_SRC}",
        f"style-src {settings.CSP_STYLE_SRC}",
        f"img-src {settings.CSP_IMG_SRC}",
        f"connect-src {settings.CSP_CONNECT_SRC}",
        f"frame-ancestors {settings.CSP_FRAME_ANCESTORS}",
        f"form-action {settings.CSP_FORM_ACTION}",
        f"report-uri {settings.CSP_REPORT_URI}",
        "report-to csp-endpoint",
    ]
    return "; ".join(directives)


_RP_TOKEN = "csp-endpoint"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security-related HTTP headers into all responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = _build_csp()
        response.headers["Report-To"] = (
            f'{{"group":"{_RP_TOKEN}","max_age":10886400,"endpoints":[{{"url":"{settings.CSP_REPORT_URI}"}}]}}'
        )
        return response
