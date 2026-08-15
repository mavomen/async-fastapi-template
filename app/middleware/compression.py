"""Brotli/gzip compression middleware for API responses."""

import gzip
import re
from typing import Any

import brotli
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

NON_COMPRESSIBLE_TYPES = re.compile(
    r"^(image/|video/|audio/|application/"
    r"(zip|gzip|x-bzip2|x\-tar|xz|x\-7z-compressed|vnd\.rar))"
)


def _parse_accept_encoding(accept_encoding: str) -> str | None:
    encodings = [e.strip().split(";")[0] for e in accept_encoding.split(",")]
    for e in encodings:
        if e == "identity":
            return None
    if "br" in encodings:
        return "br"
    if "gzip" in encodings:
        return "gzip"
    if "deflate" in encodings:
        return "deflate"
    return None


def _compress(body: bytes, algorithm: str, level: int) -> bytes:
    if algorithm == "br":
        result = brotli.compress(body, quality=level)
        return result if isinstance(result, bytes) else bytes(result)
    if algorithm in ("gzip", "deflate"):
        return gzip.compress(body, compresslevel=level)
    return body


def _is_compressible(content_type: str) -> bool:
    content_type = content_type.split(";")[0].strip()
    return not bool(NON_COMPRESSIBLE_TYPES.match(content_type))


async def _get_body(response: Response) -> bytes:
    body_iterator = getattr(response, "body_iterator", None)
    if body_iterator is not None:
        chunks: list[bytes] = []
        async for chunk in body_iterator:
            if isinstance(chunk, bytes):
                chunks.append(chunk)
        return b"".join(chunks)
    if isinstance(response.body, memoryview):
        return bytes(response.body)
    return response.body


def _skip_compression(response: Response) -> bool:
    content_type = response.headers.get("content-type", "")
    return (
        response.status_code >= 300
        or "content-encoding" in response.headers
        or not content_type
        or not _is_compressible(content_type)
    )


class CompressionMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        minimum_size: int | None = None,
        compresslevel: int | None = None,
    ) -> None:
        super().__init__(app)
        self.minimum_size = minimum_size or settings.COMPRESSION_MIN_SIZE
        self.compresslevel = compresslevel or settings.COMPRESSION_LEVEL

    async def _should_compress(self, request: Request) -> str | None:
        if not settings.COMPRESSION_ENABLED:
            return None

        accept_encoding = request.headers.get("Accept-Encoding", "")
        return _parse_accept_encoding(accept_encoding)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        algorithm = await self._should_compress(request)
        if algorithm is None:
            return await call_next(request)

        response = await call_next(request)

        if _skip_compression(response):
            return response

        content_length = response.headers.get("content-length")
        if content_length is not None and int(content_length) < self.minimum_size:
            return response

        body = await _get_body(response)

        headers = dict(response.headers)
        headers["Content-Length"] = str(len(body))
        if len(body) < self.minimum_size:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

        compressed = _compress(body, algorithm, self.compresslevel)

        headers["Content-Encoding"] = algorithm
        headers["Vary"] = "Accept-Encoding"
        headers["Content-Length"] = str(len(compressed))

        return Response(
            content=compressed,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
