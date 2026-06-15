"""Double-submit cookie CSRF protection for the admin dashboard."""

import hashlib
import hmac
import secrets

from fastapi import Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


def _sign_token(value: str, secret: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def _verify_token(value: str, signature: str, secret: str) -> bool:
    expected = _sign_token(value, secret)
    return hmac.compare_digest(expected, signature)


def _make_token(secret: str) -> str:
    raw = secrets.token_hex(8)
    sig = _sign_token(raw, secret)
    return raw + sig


class CSRFTokenMiddleware(BaseHTTPMiddleware):
    """Protect admin POST/PUT/DELETE routes with a double-submit cookie pattern."""

    def __init__(self, app, secret: str | None = None, cookie_name: str = "csrf_token"):
        super().__init__(app)
        self._secret = secret or settings.SECRET_KEY
        self._cookie_name = cookie_name
        self._ttl = 3600

    async def _validate_request(self, request: Request) -> PlainTextResponse | None:
        cookie_token = request.cookies.get(self._cookie_name, "")
        header_token = request.headers.get("X-CSRF-Token", "")
        if not header_token:
            form = await request.form()
            raw = form.get("csrf_token", "")
            header_token = raw if isinstance(raw, str) else ""
        if not header_token or not cookie_token:
            return PlainTextResponse("CSRF token missing", status_code=403)

        cookie_value, cookie_sig = cookie_token[:16], cookie_token[16:]
        header_value, header_sig = header_token[:16], header_token[16:]

        if not _verify_token(cookie_value, cookie_sig, self._secret):
            return PlainTextResponse("CSRF cookie invalid", status_code=403)
        if not _verify_token(header_value, header_sig, self._secret):
            return PlainTextResponse("CSRF token invalid", status_code=403)
        if not hmac.compare_digest(cookie_value, header_value):
            return PlainTextResponse("CSRF token mismatch", status_code=403)
        return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/admin") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            error = await self._validate_request(request)
            if error:
                return error

        response = await call_next(request)

        if path.startswith("/admin") and request.method == "GET":
            token = _make_token(self._secret)
            response.set_cookie(
                key=self._cookie_name,
                value=token,
                max_age=self._ttl,
                httponly=True,
                samesite="lax",
            )

        return response
