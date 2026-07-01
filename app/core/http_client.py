"""Shared HTTP client with connection pooling for outbound requests."""

import httpx

from app.core.config import settings


class HttpClient:
    """Manages a shared httpx.AsyncClient with keep-alive connection pooling.

    Follows the same lifecycle pattern as RedisCache:
    - connect() on app startup
    - disconnect() on app shutdown
    - get_client() returns the shared client for use in request handlers
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """Initialize the shared HTTP client with connection pool limits."""
        if self._client is not None:
            await self._client.aclose()

        limits = httpx.Limits(
            max_keepalive_connections=settings.HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=settings.HTTP_CLIENT_KEEPALIVE_EXPIRY,
        )
        timeout = httpx.Timeout(settings.HTTP_CLIENT_TIMEOUT)
        self._client = httpx.AsyncClient(limits=limits, timeout=timeout)

    async def disconnect(self) -> None:
        """Close the shared HTTP client and release connections."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def get_client(self) -> httpx.AsyncClient:
        """Return the shared HTTP client.

        Raises RuntimeError if connect() has not been called.
        """
        if self._client is None:
            raise RuntimeError("HttpClient is not connected — call connect() first")
        return self._client


http_client = HttpClient()
