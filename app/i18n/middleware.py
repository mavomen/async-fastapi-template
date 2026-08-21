"""Middleware that resolves the request locale."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings


class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.locale = self._resolve_locale(request)
        response = await call_next(request)
        response.headers["Content-Language"] = request.state.locale
        return response

    @staticmethod
    def _resolve_locale(request: Request) -> str:
        """Resolve locale from ?lang= override, then Accept-Language, then default."""
        query_lang = request.query_params.get("lang")
        if query_lang:
            candidate = query_lang.split("-")[0].lower()
            if candidate in settings.SUPPORTED_LOCALES:
                return candidate
        accept_language = request.headers.get("Accept-Language", "")
        primary = accept_language.split(",")[0].split(";")[0].strip()
        if primary:
            candidate = primary.split("-")[0].lower()
            if candidate in settings.SUPPORTED_LOCALES:
                return candidate
        return settings.DEFAULT_LOCALE
