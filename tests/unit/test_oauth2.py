"""Tests for OAuth2 social login utility functions."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.auth.oauth2 import (
    exchange_code,
    generate_oauth_state,
    get_authorize_url,
    get_provider_meta,
    get_user_info,
    parse_user_info,
)


class TestGetProviderMeta:
    def test_returns_meta_for_known_provider(self):
        meta = get_provider_meta("google")
        assert meta["authorize_url"] == "https://accounts.google.com/o/oauth2/v2/auth"

    def test_raises_for_unknown_provider(self):
        with pytest.raises(ValueError, match="Unsupported OAuth provider"):
            get_provider_meta("unknown")


class TestGetAuthorizeUrl:
    @patch("app.auth.oauth2._get_client_credentials", return_value=("my-id", "my-secret"))
    def test_returns_correct_url(self, _mock_creds):
        url = get_authorize_url("github", "state123", "http://localhost:8000/callback")
        assert url.startswith("https://github.com/login/oauth/authorize")
        assert "client_id=my-id" in url
        assert "state=state123" in url
        assert "response_type=code" in url

    @patch("app.auth.oauth2._get_client_credentials", return_value=("my-id", "my-secret"))
    def test_includes_scopes(self, _mock_creds):
        url = get_authorize_url("google", "s", "http://localhost:8000/callback")
        assert "scope=" in url
        assert "openid" in url


class TestExchangeCode:
    @pytest.mark.asyncio
    @patch("app.auth.oauth2._get_client_credentials", return_value=("cid", "cs"))
    async def test_exchange_success(self, _mock_creds, mocker):
        mock_post = mocker.patch("httpx.AsyncClient.post")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "at123",
            "refresh_token": "rt123",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await exchange_code("google", "code123", "http://localhost:8000/callback")
        assert result["access_token"] == "at123"
        assert result["refresh_token"] == "rt123"

    @pytest.mark.asyncio
    @patch("app.auth.oauth2._get_client_credentials", return_value=("cid", "cs"))
    async def test_exchange_failure_raises(self, _mock_creds, mocker):
        mock_post = mocker.patch("httpx.AsyncClient.post")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
        mock_post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await exchange_code("google", "bad", "http://localhost:8000/callback")


class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_fetch_success(self, mocker):
        mock_get = mocker.patch("httpx.AsyncClient.get")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "email": "test@example.com",
            "name": "Test User",
            "id": "12345",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = await get_user_info("google", "at123")
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_fetch_failure_raises(self, mocker):
        mock_get = mocker.patch("httpx.AsyncClient.get")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
        mock_get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await get_user_info("google", "bad")


class TestParseUserInfo:
    def test_google_format(self):
        raw = {"email": "alice@gmail.com", "name": "Alice", "id": "12345"}
        result = parse_user_info("google", raw)
        assert result["email"] == "alice@gmail.com"
        assert result["name"] == "Alice"
        assert result["provider_id"] == "12345"

    def test_github_format(self):
        raw = {"email": "bob@github.com", "name": "Bob", "id": 67890}
        result = parse_user_info("github", raw)
        assert result["email"] == "bob@github.com"
        assert result["provider_id"] == "67890"

    def test_gitlab_format(self):
        raw = {"email": "carol@gitlab.com", "name": "Carol", "id": "abc123"}
        result = parse_user_info("gitlab", raw)
        assert result["email"] == "carol@gitlab.com"
        assert result["provider_id"] == "abc123"

    def test_returns_empty_string_for_missing_fields(self):
        raw: dict = {}
        result = parse_user_info("google", raw)
        assert result["email"] == ""
        assert result["provider_id"] == ""


class TestGenerateOAuthState:
    def test_generates_string(self):
        state = generate_oauth_state()
        assert isinstance(state, str)
        assert len(state) > 16

    def test_generates_unique_values(self):
        states = {generate_oauth_state() for _ in range(100)}
        assert len(states) == 100


class TestOAuthService:
    @pytest.mark.asyncio
    async def test_store_and_consume_state(self, mocker):
        from app.services.oauth2 import consume_oauth_state, store_oauth_state

        mock_cache_set = mocker.patch("app.services.oauth2.cache.set")
        mock_cache_get = mocker.patch("app.services.oauth2.cache.get")
        mock_cache_delete = mocker.patch("app.services.oauth2.cache.delete")

        mock_cache_get.return_value = {"provider": "google"}

        await store_oauth_state("mystate", {"provider": "google"})
        mock_cache_set.assert_called_once()

        result = await consume_oauth_state("mystate")
        assert result == {"provider": "google"}
        mock_cache_delete.assert_called_once_with("oauth_state:mystate")

    @pytest.mark.asyncio
    async def test_consume_invalid_state_returns_none(self, mocker):
        from app.services.oauth2 import consume_oauth_state

        mocker.patch("app.services.oauth2.cache.get", return_value=None)

        result = await consume_oauth_state("invalid")
        assert result is None
