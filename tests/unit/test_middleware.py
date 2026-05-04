"""Unit tests for custom middlewares."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.correlation import CorrelationIDMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.error_logging import error_logging_middleware


@pytest.mark.asyncio
async def test_correlation_id_middleware_injects_header():
    middleware = CorrelationIDMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.headers = {}
    request.state = MagicMock()
    call_next = AsyncMock(return_value=Response())

    response = await middleware.dispatch(request, call_next)

    assert "X-Correlation-ID" in response.headers
    assert request.state.correlation_id is not None


@pytest.mark.asyncio
async def test_correlation_id_middleware_uses_existing():
    middleware = CorrelationIDMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.headers = {"X-Correlation-ID": "custom-id"}
    request.state = MagicMock()
    call_next = AsyncMock(return_value=Response())

    response = await middleware.dispatch(request, call_next)

    assert response.headers["X-Correlation-ID"] == "custom-id"
    assert request.state.correlation_id == "custom-id"


@pytest.mark.asyncio
async def test_error_logging_middleware_passes_through():
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/test"
    call_next = AsyncMock(return_value=Response())

    # Should just pass through without error
    response = await error_logging_middleware(request, call_next)
    assert response.status_code == 200
    call_next.assert_awaited_once()
