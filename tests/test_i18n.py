"""Tests for i18n: translations catalog, locale middleware, localized error responses, and locale-aware emails."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.api.error_handlers import configure_exception_handlers
from app.core.exceptions import NotFoundException
from app.i18n.middleware import LocaleMiddleware
from app.i18n.translations import get_translations, translate
from app.services.email import EmailService

# Error codes that must be present in every supported locale's catalog.
# Derived from app/core/exceptions.py plus VALIDATION_ERROR / HTTP_ERROR from the handlers.
EXPECTED_ERROR_CODES: tuple[str, ...] = (
    "APP_ERROR",
    "BAD_REQUEST",
    "CONFLICT",
    "FORBIDDEN",
    "HTTP_ERROR",
    "INTERNAL_ERROR",
    "LOCKED_OUT",
    "NOT_FOUND",
    "RATE_LIMITED",
    "UNAUTHORIZED",
    "VALIDATION_ERROR",
)


class TestTranslate:
    def test_translate_english_key(self) -> None:
        assert translate("NOT_FOUND", "en") == "Resource not found"

    def test_translate_spanish_key(self) -> None:
        assert translate("NOT_FOUND", "es") == "Recurso no encontrado"

    def test_translate_unknown_locale_falls_back_to_english(self) -> None:
        assert translate("NOT_FOUND", "fr") == "Resource not found"

    def test_translate_unknown_key_returns_key(self) -> None:
        assert translate("UNKNOWN_KEY", "en") == "UNKNOWN_KEY"

    def test_translate_with_kwargs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Interpolation substitutes {placeholders} via str.format."""
        monkeypatch.setitem(
            get_translations("en"), "TEST_INTERPOLATION", "Retry in {seconds} seconds"
        )
        assert translate("TEST_INTERPOLATION", "en", seconds="30") == "Retry in 30 seconds"

    def test_get_translations_returns_catalog(self) -> None:
        catalog = get_translations("en")
        assert isinstance(catalog, dict)
        assert "NOT_FOUND" in catalog
        assert catalog["NOT_FOUND"] == "Resource not found"

    def test_get_translations_unknown_locale_falls_back_to_default(self) -> None:
        """Unknown locales resolve to the default-locale catalog rather than raising."""
        assert get_translations("fr") == get_translations("en")


class TestGetTranslations:
    def test_english_catalog_has_all_exception_keys(self) -> None:
        catalog = get_translations("en")
        missing = [code for code in EXPECTED_ERROR_CODES if code not in catalog]
        assert not missing, f"Missing keys in en catalog: {missing}"

    def test_spanish_catalog_has_all_exception_keys(self) -> None:
        catalog = get_translations("es")
        missing = [code for code in EXPECTED_ERROR_CODES if code not in catalog]
        assert not missing, f"Missing keys in es catalog: {missing}"

    def test_english_and_spanish_differ(self) -> None:
        en = get_translations("en")
        es = get_translations("es")
        differing = [key for key in en if key in es and en[key] != es[key]]
        assert differing, "English and Spanish catalogs are identical"


@pytest.fixture
def i18n_app() -> FastAPI:
    """Minimal app with only LocaleMiddleware and a locale-echo endpoint."""
    app = FastAPI()
    app.add_middleware(LocaleMiddleware)

    @app.get("/locale")
    async def get_locale(request: Request) -> dict[str, str]:
        return {"locale": getattr(request.state, "locale", "unknown")}

    return app


@pytest.fixture
async def i18n_client(i18n_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=i18n_app),
        base_url="http://test",
    ) as client:
        yield client


class TestLocaleMiddleware:
    @pytest.mark.asyncio
    async def test_default_locale_is_english(self, i18n_client: AsyncClient) -> None:
        resp = await i18n_client.get("/locale")
        assert resp.headers["Content-Language"] == "en"
        assert resp.json()["locale"] == "en"

    @pytest.mark.asyncio
    async def test_spanish_accept_language_sets_locale(self, i18n_client: AsyncClient) -> None:
        resp = await i18n_client.get("/locale", headers={"Accept-Language": "es"})
        assert resp.headers["Content-Language"] == "es"
        assert resp.json()["locale"] == "es"

    @pytest.mark.asyncio
    async def test_unsupported_locale_falls_back(self, i18n_client: AsyncClient) -> None:
        resp = await i18n_client.get("/locale", headers={"Accept-Language": "fr"})
        assert resp.headers["Content-Language"] == "en"
        assert resp.json()["locale"] == "en"

    @pytest.mark.asyncio
    async def test_lang_query_param_overrides(self, i18n_client: AsyncClient) -> None:
        resp = await i18n_client.get(
            "/locale",
            params={"lang": "es"},
            headers={"Accept-Language": "en"},
        )
        assert resp.headers["Content-Language"] == "es"
        assert resp.json()["locale"] == "es"

    @pytest.mark.asyncio
    async def test_locale_stored_in_request_state(self, i18n_client: AsyncClient) -> None:
        resp = await i18n_client.get("/locale", headers={"Accept-Language": "es"})
        assert resp.json()["locale"] == "es"


class ItemCreate(BaseModel):
    name: str
    quantity: int


@pytest.fixture
def error_app() -> FastAPI:
    """App with LocaleMiddleware plus localized exception handlers.

    LocaleMiddleware is required: the exception handlers read request.state.locale,
    which only the middleware populates from Accept-Language / ?lang=.
    """
    app = FastAPI()
    app.add_middleware(LocaleMiddleware)
    configure_exception_handlers(app)

    @app.get("/resources/{resource_id}")
    async def get_resource(resource_id: int) -> dict[str, int]:
        raise NotFoundException

    @app.post("/items")
    async def create_item(item: ItemCreate) -> dict[str, str]:
        return {"name": item.name}

    return app


@pytest.fixture
async def error_client(error_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=error_app),
        base_url="http://test",
    ) as client:
        yield client


class TestExceptionHandlerI18n:
    @pytest.mark.asyncio
    async def test_not_found_english(self, error_client: AsyncClient) -> None:
        resp = await error_client.get("/resources/1", headers={"Accept-Language": "en"})
        assert resp.status_code == 404
        body = resp.json()
        assert body["error_code"] == "NOT_FOUND"
        assert body["detail"] == "Resource not found"

    @pytest.mark.asyncio
    async def test_not_found_spanish(self, error_client: AsyncClient) -> None:
        resp = await error_client.get("/resources/1", headers={"Accept-Language": "es"})
        assert resp.status_code == 404
        body = resp.json()
        assert body["error_code"] == "NOT_FOUND"
        assert body["detail"] == "Recurso no encontrado"

    @pytest.mark.asyncio
    async def test_unmatched_route_uses_http_error_translation(
        self, error_client: AsyncClient
    ) -> None:
        resp = await error_client.get("/nonexistent", headers={"Accept-Language": "es"})
        assert resp.status_code == 404
        body = resp.json()
        assert body["error_code"] == "HTTP_ERROR"
        assert body["detail"] == "Error HTTP"

    @pytest.mark.asyncio
    async def test_validation_error_english(self, error_client: AsyncClient) -> None:
        resp = await error_client.post(
            "/items",
            json={"name": "widget"},
            headers={"Accept-Language": "en"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error_code"] == "VALIDATION_ERROR"
        assert body["detail"] == "Validation error"

    @pytest.mark.asyncio
    async def test_validation_error_spanish(self, error_client: AsyncClient) -> None:
        resp = await error_client.post(
            "/items",
            json={"name": "widget"},
            headers={"Accept-Language": "es"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error_code"] == "VALIDATION_ERROR"
        assert body["detail"] == "Error de validación"


def _subject_of(mock_send: AsyncMock) -> str:
    """Extract the subject argument from a mocked send_email call."""
    call = mock_send.await_args
    assert call is not None
    if "subject" in call.kwargs:
        return str(call.kwargs["subject"])
    return str(call.args[1])


class TestEmailServiceLocale:
    @pytest.mark.asyncio
    async def test_verification_email_english_subject(self) -> None:
        service = EmailService()
        with patch.object(EmailService, "send_email", new_callable=AsyncMock) as mock_send:
            await service.send_verification_email(
                to_email="user@example.com", token="token-123", locale="en"
            )
        mock_send.assert_awaited_once()
        assert _subject_of(mock_send) == "Verify your email"

    @pytest.mark.asyncio
    async def test_verification_email_spanish_subject(self) -> None:
        service = EmailService()
        with patch.object(EmailService, "send_email", new_callable=AsyncMock) as mock_send:
            await service.send_verification_email(
                to_email="user@example.com", token="token-123", locale="es"
            )
        mock_send.assert_awaited_once()
        assert _subject_of(mock_send) == "Verifica tu correo electrónico"

    @pytest.mark.asyncio
    async def test_magic_link_email_english_subject(self) -> None:
        service = EmailService()
        with patch.object(EmailService, "send_email", new_callable=AsyncMock) as mock_send:
            await service.send_magic_link_email(
                to_email="user@example.com", token="token-123", locale="en"
            )
        mock_send.assert_awaited_once()
        assert _subject_of(mock_send) == "Your sign-in link"

    @pytest.mark.asyncio
    async def test_magic_link_email_spanish_subject(self) -> None:
        service = EmailService()
        with patch.object(EmailService, "send_email", new_callable=AsyncMock) as mock_send:
            await service.send_magic_link_email(
                to_email="user@example.com", token="token-123", locale="es"
            )
        mock_send.assert_awaited_once()
        assert _subject_of(mock_send) == "Tu enlace de inicio de sesión"
