"""Tests for per-user rate limiting middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.per_user_rate_limit import PerUserRateLimitMiddleware


@pytest.mark.asyncio
async def test_per_user_rate_limit_dispatch():
    middleware = PerUserRateLimitMiddleware(app=None)
    request = MagicMock(spec=Request)
    request.state.user_id = None  # no authenticated user, falls back to IP
    call_next = AsyncMock(return_value=Response(status_code=200))
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200
    call_next.assert_awaited_once()
