"""Tests for request ID middleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from app.middleware.request_id import RequestIDMiddleware


@pytest.mark.asyncio
async def test_request_id_sets_span():
    middleware = RequestIDMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.state.correlation_id = "my-corr-id"
    call_next = AsyncMock()

    mock_span = MagicMock()
    with patch("app.middleware.request_id.trace.get_current_span", return_value=mock_span):
        await middleware.dispatch(request, call_next)
    mock_span.set_attribute.assert_called_once_with("correlation_id", "my-corr-id")
