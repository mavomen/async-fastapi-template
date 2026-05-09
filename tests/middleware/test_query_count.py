"""Tests for query count middleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.query_count import QueryCountMiddleware


@pytest.mark.asyncio
async def test_query_count_middleware_sets_header():
    middleware = QueryCountMiddleware(app=None)
    request = MagicMock(spec=Request)
    call_next = AsyncMock(return_value=Response(status_code=200))
    with patch("app.middleware.query_count.http_queries_per_request") as mock_hist:
        response = await middleware.dispatch(request, call_next)
    assert response.headers["X-Query-Count"] == "0"
    mock_hist.observe.assert_called_once_with(0)
