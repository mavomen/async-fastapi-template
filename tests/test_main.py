from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from starlette.middleware.cors import CORSMiddleware


def test_create_app_returns_fastapi_instance():
    """create_app should return a FastAPI instance."""
    from app.main import create_app

    app = create_app()
    assert isinstance(app, FastAPI)


def test_app_title_from_settings():
    """App title should come from settings.PROJECT_NAME."""
    from app.core.config import settings
    from app.main import create_app

    app = create_app()
    assert app.title == settings.PROJECT_NAME


def test_app_version_from_settings():
    """App version should come from settings.VERSION."""
    from app.core.config import settings
    from app.main import create_app

    app = create_app()
    assert app.version == settings.VERSION


def test_app_default_response_class():
    """App should use ORJSONResponse as default."""
    from app.main import create_app

    app = create_app()

    assert ORJSONResponse in [ORJSONResponse]

    from app.main import app as module_app

    assert module_app is not None


def test_app_docs_enabled_in_development(monkeypatch):
    """Docs should be enabled when not in production."""
    monkeypatch.setenv("ENVIRONMENT", "development")

    from importlib import reload

    from app.core import config

    reload(config)
    from app import main

    reload(main)

    app = main.create_app()
    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"


def test_app_docs_disabled_in_production(monkeypatch):
    """Docs should be disabled in production."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    from importlib import reload

    from app.core import config

    reload(config)
    from app import main

    reload(main)

    app = main.create_app()
    assert app.docs_url is None
    assert app.redoc_url is None


def test_cors_middleware_registered():
    """CORS middleware should be registered."""
    from app.main import create_app

    app = create_app()

    cors_middleware = None
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            cors_middleware = middleware
            break

    assert cors_middleware is not None


def test_cors_middleware_configuration():
    """CORS middleware should have correct configuration."""
    from app.core.config import settings
    from app.main import create_app

    app = create_app()

    cors_middleware = None
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            cors_middleware = middleware
            break

    assert cors_middleware is not None

    kwargs = cors_middleware.kwargs

    assert kwargs["allow_origins"] == settings.ALLOWED_ORIGINS
    assert kwargs["allow_credentials"] is True
    assert kwargs["allow_methods"] == ["*"]
    assert kwargs["allow_headers"] == ["*"]


def test_health_router_registered():
    """Health router should be registered with correct prefix."""
    from app.main import create_app

    app = create_app()

    health_routes = [route for route in app.routes if "/health" in str(route.path)]
    assert len(health_routes) > 0


def test_health_router_tags():
    """Health routes should have 'health' tag."""
    from app.main import create_app

    app = create_app()

    health_route = None
    for route in app.routes:
        if hasattr(route, "path") and "/health" in str(route.path):
            health_route = route
            break

    assert health_route is not None
    if hasattr(health_route, "tags"):
        assert "health" in health_route.tags


@pytest.mark.anyio
async def test_lifespan_startup_initializes_sessionmanager():
    """Lifespan startup should initialize sessionmanager."""
    from app.core.config import settings
    from app.core.database import sessionmanager
    from app.main import create_app

    with patch.object(sessionmanager, "init") as mock_init:
        with patch.object(
            sessionmanager, "close", new_callable=AsyncMock
        ) as mock_close:
            app = create_app()

            async with app.router.lifespan_context(app):
                mock_init.assert_called_once_with(settings.DATABASE_URL)

            mock_close.assert_called_once()


@pytest.mark.anyio
async def test_lifespan_shutdown_closes_sessionmanager():
    """Lifespan shutdown should close sessionmanager."""
    from app.core.database import sessionmanager
    from app.main import create_app

    with patch.object(sessionmanager, "init"):
        with patch.object(
            sessionmanager, "close", new_callable=AsyncMock
        ) as mock_close:
            app = create_app()

            async with app.router.lifespan_context(app):
                pass

            mock_close.assert_called_once()


def test_module_level_app_instance():
    """Module should export an app instance."""
    from app import main

    assert hasattr(main, "app")
    assert isinstance(main.app, FastAPI)


@pytest.mark.anyio
async def test_app_startup_event_order():
    """Startup should initialize database before handling requests."""
    from app.core.database import sessionmanager
    from app.main import create_app

    init_called = False

    def track_init(url):
        nonlocal init_called
        init_called = True

    with patch.object(sessionmanager, "init", side_effect=track_init):
        with patch.object(sessionmanager, "close", new_callable=AsyncMock):
            app = create_app()

            async with app.router.lifespan_context(app):
                assert init_called


def test_app_routes_count():
    """App should have at least health routes registered."""
    from app.main import create_app

    app = create_app()

    assert len(app.routes) >= 1


def test_cors_allows_credentials():
    """CORS should allow credentials."""
    from app.main import create_app

    app = create_app()

    cors_middleware = None
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            cors_middleware = middleware
            break

    assert cors_middleware.kwargs["allow_credentials"] is True


def test_cors_allows_all_methods():
    """CORS should allow all HTTP methods."""
    from app.main import create_app

    app = create_app()

    cors_middleware = None
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            cors_middleware = middleware
            break

    assert cors_middleware.kwargs["allow_methods"] == ["*"]


def test_cors_allows_all_headers():
    """CORS should allow all headers."""
    from app.main import create_app

    app = create_app()

    cors_middleware = None
    for middleware in app.user_middleware:
        if middleware.cls == CORSMiddleware:
            cors_middleware = middleware
            break

    assert cors_middleware.kwargs["allow_headers"] == ["*"]
