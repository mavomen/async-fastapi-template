"""Tests for Brotli/gzip compression middleware."""

import gzip
from unittest.mock import AsyncMock, MagicMock, patch

import brotli
import pytest
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from app.middleware.compression import (
    CompressionMiddleware,
    _compress,
    _is_compressible,
    _parse_accept_encoding,
)

TEST_BODY = b'{"key": "value", "nested": {"a": 1, "b": 2}}' * 50  # ~2KB

_ENABLED_SETTINGS = MagicMock(
    COMPRESSION_ENABLED=True, COMPRESSION_MIN_SIZE=1024, COMPRESSION_LEVEL=6
)
_DISABLED_SETTINGS = MagicMock(COMPRESSION_ENABLED=False)


class TestHelperFunctions:
    def test_parse_accept_encoding_br(self):
        assert _parse_accept_encoding("br") == "br"
        assert _parse_accept_encoding("br, gzip") == "br"
        assert _parse_accept_encoding("gzip, br") == "br"

    def test_parse_accept_encoding_gzip(self):
        assert _parse_accept_encoding("gzip") == "gzip"
        assert _parse_accept_encoding("deflate, gzip") == "gzip"

    def test_parse_accept_encoding_identity(self):
        assert _parse_accept_encoding("identity") is None
        assert _parse_accept_encoding("identity, gzip") is None

    def test_parse_accept_encoding_none(self):
        assert _parse_accept_encoding("") is None
        assert _parse_accept_encoding("*") is None

    def test_is_compressible(self):
        assert _is_compressible("application/json") is True
        assert _is_compressible("text/html; charset=utf-8") is True
        assert _is_compressible("text/plain") is True
        assert _is_compressible("application/xml") is True

    def test_is_not_compressible(self):
        assert _is_compressible("image/png") is False
        assert _is_compressible("image/webp") is False
        assert _is_compressible("video/mp4") is False
        assert _is_compressible("audio/mpeg") is False
        assert _is_compressible("application/zip") is False
        assert _is_compressible("application/gzip") is False

    def test_compress_brotli(self):
        result = _compress(b"hello world", "br", 6)
        assert brotli.decompress(result) == b"hello world"

    def test_compress_gzip(self):
        result = _compress(b"hello world", "gzip", 6)
        assert gzip.decompress(result) == b"hello world"

    def test_compress_deflate(self):
        result = _compress(b"hello world", "deflate", 6)
        assert gzip.decompress(result) == b"hello world"

    def test_compress_unknown(self):
        assert _compress(b"hello world", "unknown", 6) == b"hello world"


class TestCompressionMiddleware:
    @pytest.mark.asyncio
    async def test_brotli_compression(self):
        request = MagicMock(spec=Request)
        request.headers = {"Accept-Encoding": "br"}
        call_next = AsyncMock(
            return_value=Response(content=TEST_BODY, media_type="application/json")
        )
        middleware = CompressionMiddleware(app=None)

        with patch("app.middleware.compression.settings", _ENABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        assert response.headers["Content-Encoding"] == "br"
        assert response.headers.get("Vary") == "Accept-Encoding"
        assert brotli.decompress(response.body) == TEST_BODY

    @pytest.mark.asyncio
    async def test_gzip_compression(self):
        request = MagicMock(spec=Request)
        request.headers = {"Accept-Encoding": "gzip"}
        call_next = AsyncMock(
            return_value=Response(content=TEST_BODY, media_type="application/json")
        )
        middleware = CompressionMiddleware(app=None)

        with patch("app.middleware.compression.settings", _ENABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        assert response.headers["Content-Encoding"] == "gzip"
        assert gzip.decompress(response.body) == TEST_BODY

    @pytest.mark.asyncio
    async def test_brotli_preferred_over_gzip(self):
        request = MagicMock(spec=Request)
        request.headers = {"Accept-Encoding": "gzip, br"}
        call_next = AsyncMock(
            return_value=Response(content=TEST_BODY, media_type="application/json")
        )
        middleware = CompressionMiddleware(app=None)

        with patch("app.middleware.compression.settings", _ENABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert response.headers["Content-Encoding"] == "br"

    @pytest.mark.asyncio
    async def test_small_response_not_compressed(self):
        small_body = b'{"ok": true}'
        request = MagicMock(spec=Request)
        request.headers = {"Accept-Encoding": "br"}
        call_next = AsyncMock(
            return_value=Response(content=small_body, media_type="application/json")
        )
        middleware = CompressionMiddleware(app=None, minimum_size=1024)

        with patch("app.middleware.compression.settings", _ENABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert "Content-Encoding" not in response.headers
        assert response.body == small_body

    @pytest.mark.asyncio
    async def test_no_accept_encoding_passthrough(self):
        request = MagicMock(spec=Request)
        request.headers = {}
        call_next = AsyncMock(
            return_value=Response(content=TEST_BODY, media_type="application/json")
        )
        middleware = CompressionMiddleware(app=None)

        with patch("app.middleware.compression.settings", _ENABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert "Content-Encoding" not in response.headers
        assert response.body == TEST_BODY

    @pytest.mark.asyncio
    async def test_already_compressed_skipped(self):
        request = MagicMock(spec=Request)
        request.headers = {"Accept-Encoding": "br"}
        call_next = AsyncMock(
            return_value=Response(
                content=TEST_BODY,
                media_type="application/json",
                headers={"Content-Encoding": "gzip"},
            )
        )
        middleware = CompressionMiddleware(app=None)

        with patch("app.middleware.compression.settings", _ENABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert response.headers["Content-Encoding"] == "gzip"

    @pytest.mark.asyncio
    async def test_non_compressible_type_skipped(self):
        request = MagicMock(spec=Request)
        request.headers = {"Accept-Encoding": "br"}
        call_next = AsyncMock(return_value=Response(content=TEST_BODY, media_type="image/png"))
        middleware = CompressionMiddleware(app=None)

        with patch("app.middleware.compression.settings", _ENABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert "Content-Encoding" not in response.headers

    @pytest.mark.asyncio
    async def test_redirect_not_compressed(self):
        request = MagicMock(spec=Request)
        request.headers = {"Accept-Encoding": "br"}
        call_next = AsyncMock(return_value=Response(status_code=307))
        middleware = CompressionMiddleware(app=None)

        with patch("app.middleware.compression.settings", _ENABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert "Content-Encoding" not in response.headers

    @pytest.mark.asyncio
    async def test_streaming_response_body_captured_and_compressed(self):
        async def _body_iter():
            yield TEST_BODY

        request = MagicMock(spec=Request)
        request.headers = {"Accept-Encoding": "br"}
        call_next = AsyncMock(
            return_value=StreamingResponse(content=_body_iter(), media_type="text/plain")
        )
        middleware = CompressionMiddleware(app=None)

        with patch("app.middleware.compression.settings", _ENABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        assert response.headers["Content-Encoding"] == "br"
        assert brotli.decompress(response.body) == TEST_BODY

    @pytest.mark.asyncio
    async def test_compression_disabled_by_settings(self):
        request = MagicMock(spec=Request)
        request.headers = {"Accept-Encoding": "br"}
        call_next = AsyncMock(
            return_value=Response(content=TEST_BODY, media_type="application/json")
        )
        middleware = CompressionMiddleware(app=None)

        with patch("app.middleware.compression.settings", _DISABLED_SETTINGS):
            response = await middleware.dispatch(request, call_next)

        assert "Content-Encoding" not in response.headers
        assert response.body == TEST_BODY
