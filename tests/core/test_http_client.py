"""Tests for shared HTTP client connection pooling."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.http_client import HttpClient


class TestHttpClient:
    @pytest.mark.asyncio
    async def test_connect_creates_client(self):
        client = HttpClient()
        assert client._client is None

        await client.connect()

        assert client._client is not None
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_get_client_returns_same_instance(self):
        client = HttpClient()
        await client.connect()

        c1 = client.get_client()
        c2 = client.get_client()

        assert c1 is c2
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_get_client_before_connect_raises(self):
        client = HttpClient()

        with pytest.raises(RuntimeError, match="HttpClient is not connected"):
            client.get_client()

    @pytest.mark.asyncio
    async def test_disconnect_closes_and_clears(self):
        client = HttpClient()
        await client.connect()

        await client.disconnect()

        assert client._client is None
        with pytest.raises(RuntimeError, match="HttpClient is not connected"):
            client.get_client()

    @pytest.mark.asyncio
    async def test_connect_idempotent_replaces_old(self):
        client = HttpClient()
        await client.connect()
        first = client.get_client()

        await client.connect()
        second = client.get_client()

        assert first is not second
        assert client._client is second
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_idempotent(self):
        client = HttpClient()

        await client.disconnect()
        await client.disconnect()

        assert client._client is None

    @pytest.mark.asyncio
    async def test_uses_settings_for_limits(self):
        mock_settings = MagicMock(
            HTTP_CLIENT_TIMEOUT=15,
            HTTP_CLIENT_MAX_KEEPALIVE_CONNECTIONS=5,
            HTTP_CLIENT_KEEPALIVE_EXPIRY=60,
        )

        with patch("app.core.http_client.settings", mock_settings):
            client = HttpClient()
            await client.connect()
            assert client._client is not None
            await client.disconnect()
