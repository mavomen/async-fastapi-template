"""Tests for cache decorator and invalidation."""

# from unittest.mock import AsyncMock, patch
#
# import pytest
# from httpx import AsyncClient
#
# from app.core.cache import cache
# from app.decorators.cache import cached
#
#
# @pytest.mark.asyncio
# async def test_cache_set_get_delete():
#     await cache.connect()
#     try:
#         await cache.set("test_key", {"a": 1}, ttl=10)
#         val = await cache.get("test_key")
#         assert val == {"a": 1}
#         await cache.delete("test_key")
#         val = await cache.get("test_key")
#         assert val is None
#     finally:
#         await cache.disconnect()
#
#
# @pytest.mark.asyncio
# async def test_cache_decorator(monkeypatch):
#     from fastapi import FastAPI, Request
#     from fastapi.testclient import TestClient
#
#     app = FastAPI()
#
#     # Mock the cache methods
#     mock_cache = AsyncMock()
#     monkeypatch.setattr("app.decorators.cache.cache", mock_cache)
#
#     @app.get("/cached")
#     @cached(ttl=10)
#     async def cached_endpoint(request: Request):
#         return {"data": "uncached"}
#
#     client = TestClient(app)
#
#     # First call: no cache, should call endpoint
#     mock_cache.get.return_value = None
#     response = client.get("/cached")
#     assert response.status_code == 200
#     assert response.json() == {"data": "uncached"}
#     # Verify set was called
#     assert mock_cache.set.called
#
#     # Second call: cached response
#     mock_cache.get.return_value = {"status": 200, "body": {"data": "cached"}}
#     response = client.get("/cached")
#     assert response.status_code == 200
#     assert response.json() == {"data": "cached"}
#
#
# @pytest.mark.asyncio
# async def test_cache_invalidation_by_prefix():
#     await cache.connect()
#     try:
#         await cache.set("prefix:1", "a")
#         await cache.set("prefix:2", "b")
#         await cache.set("other", "c")
#
#         # Invalidate prefix
#         from app.utils.cache_invalidation import invalidate_by_prefix
#
#         await invalidate_by_prefix("prefix")
#
#         assert await cache.get("prefix:1") is None
#         assert await cache.get("prefix:2") is None
#         assert await cache.get("other") == "c"
#     finally:
#         await cache.disconnect()
