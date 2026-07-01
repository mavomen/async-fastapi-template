"""Tests for OAuth2 social login endpoints."""

from unittest.mock import MagicMock


class TestOAuthLoginEndpoint:
    def test_login_returns_authorize_url(self, client, mocker):
        mocker.patch(
            "app.auth.oauth2._get_client_credentials", return_value=("google-id", "google-secret")
        )
        resp = client.get("/api/v1/auth/oauth/login?provider=google")
        assert resp.status_code == 200
        data = resp.json()
        assert "authorize_url" in data
        assert "state" in data
        assert data["authorize_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth")

    def test_login_with_github(self, client, mocker):
        mocker.patch(
            "app.auth.oauth2._get_client_credentials", return_value=("github-id", "github-secret")
        )
        resp = client.get("/api/v1/auth/oauth/login?provider=github")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authorize_url"].startswith("https://github.com/login/oauth/authorize")

    def test_login_with_unknown_provider(self, client):
        resp = client.get("/api/v1/auth/oauth/login?provider=unknown")
        assert resp.status_code == 400

    def test_login_with_unconfigured_provider(self, client, mocker):
        mocker.patch(
            "app.auth.oauth2._get_client_credentials",
            side_effect=ValueError("OAuth provider 'google' is not configured"),
        )
        resp = client.get("/api/v1/auth/oauth/login?provider=google")
        assert resp.status_code == 400


class TestOAuthCallbackEndpoint:
    def test_callback_with_invalid_state(self, client, mocker):
        mocker.patch("app.api.endpoints.auth.consume_oauth_state", return_value=None)
        mocker.patch("app.auth.oauth2._get_client_credentials", return_value=("id", "secret"))

        resp = client.get("/api/v1/auth/oauth/callback?provider=google&code=testcode&state=bogus")
        assert resp.status_code == 400
        assert "state" in resp.text.lower()

    def test_callback_with_exchange_failure(self, client, mocker):
        mocker.patch(
            "app.api.endpoints.auth.consume_oauth_state", return_value={"provider": "google"}
        )
        mocker.patch("app.auth.oauth2._get_client_credentials", return_value=("id", "secret"))
        mocker.patch("app.api.endpoints.auth.exchange_code", side_effect=Exception("bad code"))

        resp = client.get("/api/v1/auth/oauth/callback?provider=google&code=bad&state=validstate")
        assert resp.status_code == 400
        assert "bad code" in resp.text.lower()

    def test_callback_with_userinfo_failure(self, client, mocker):
        mocker.patch(
            "app.api.endpoints.auth.consume_oauth_state", return_value={"provider": "google"}
        )
        mocker.patch("app.auth.oauth2._get_client_credentials", return_value=("id", "secret"))
        mocker.patch(
            "app.api.endpoints.auth.exchange_code",
            return_value={"access_token": "at", "refresh_token": "rt"},
        )
        mocker.patch("app.api.endpoints.auth.get_user_info", side_effect=Exception("API error"))

        resp = client.get("/api/v1/auth/oauth/callback?provider=google&code=code&state=validstate")
        assert resp.status_code == 400

    def test_callback_creates_new_user(self, client, mocker):
        mocker.patch(
            "app.api.endpoints.auth.consume_oauth_state", return_value={"provider": "google"}
        )
        mocker.patch("app.auth.oauth2._get_client_credentials", return_value=("id", "secret"))
        mocker.patch(
            "app.api.endpoints.auth.exchange_code",
            return_value={"access_token": "at", "refresh_token": "rt"},
        )
        mocker.patch(
            "app.api.endpoints.auth.get_user_info",
            return_value={"email": "new@example.com", "name": "New", "id": "999"},
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get_by_oauth", return_value=None)
        mocker.patch("app.api.endpoints.auth.crud_user.get_by_email", return_value=None)
        mocker.patch("app.api.endpoints.auth.crud_user.create_oauth_user")
        mocker.patch(
            "app.api.endpoints.auth._issue_tokens",
            return_value={"access_token": "at", "refresh_token": "rt", "token_type": "bearer"},
        )

        resp = client.get("/api/v1/auth/oauth/callback?provider=google&code=code&state=validstate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "at"

    def test_callback_links_existing_user(self, client, mocker):
        mock_user = MagicMock()
        mock_user.oauth_provider_id = None
        mock_user.is_active = True
        mock_user.id = 1
        mock_user.tenant_id = 1

        mocker.patch(
            "app.api.endpoints.auth.consume_oauth_state", return_value={"provider": "google"}
        )
        mocker.patch("app.auth.oauth2._get_client_credentials", return_value=("id", "secret"))
        mocker.patch("app.api.endpoints.auth.exchange_code", return_value={"access_token": "at"})
        mocker.patch(
            "app.api.endpoints.auth.get_user_info",
            return_value={"email": "exist@example.com", "name": "Exist", "id": "123"},
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get_by_oauth", return_value=None)
        mocker.patch("app.api.endpoints.auth.crud_user.get_by_email", return_value=mock_user)
        mocker.patch("app.api.endpoints.auth.crud_user.link_oauth_account", return_value=mock_user)
        mocker.patch(
            "app.api.endpoints.auth._issue_tokens",
            return_value={"access_token": "at", "refresh_token": "rt", "token_type": "bearer"},
        )

        resp = client.get("/api/v1/auth/oauth/callback?provider=google&code=code&state=validstate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "at"

    def test_callback_returns_existing_user_by_oauth(self, client, mocker):
        mock_user = MagicMock()
        mock_user.oauth_provider = "google"
        mock_user.oauth_provider_id = "123"
        mock_user.is_active = True
        mock_user.id = 1
        mock_user.tenant_id = 1

        mocker.patch(
            "app.api.endpoints.auth.consume_oauth_state", return_value={"provider": "google"}
        )
        mocker.patch("app.auth.oauth2._get_client_credentials", return_value=("id", "secret"))
        mocker.patch("app.api.endpoints.auth.exchange_code", return_value={"access_token": "at"})
        mocker.patch(
            "app.api.endpoints.auth.get_user_info",
            return_value={"email": "exist@example.com", "name": "Exist", "id": "123"},
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get_by_oauth", return_value=mock_user)
        mocker.patch(
            "app.api.endpoints.auth._issue_tokens",
            return_value={"access_token": "at", "refresh_token": "rt", "token_type": "bearer"},
        )

        resp = client.get("/api/v1/auth/oauth/callback?provider=google&code=code&state=validstate")
        assert resp.status_code == 200

    def test_callback_conflict_on_different_oauth_account(self, client, mocker):
        mock_user = MagicMock()
        mock_user.oauth_provider = "github"
        mock_user.oauth_provider_id = "999"
        mock_user.is_active = True
        mock_user.id = 1
        mock_user.tenant_id = 1

        mocker.patch(
            "app.api.endpoints.auth.consume_oauth_state", return_value={"provider": "google"}
        )
        mocker.patch("app.auth.oauth2._get_client_credentials", return_value=("id", "secret"))
        mocker.patch("app.api.endpoints.auth.exchange_code", return_value={"access_token": "at"})
        mocker.patch(
            "app.api.endpoints.auth.get_user_info",
            return_value={"email": "conflict@example.com", "name": "Conflict", "id": "123"},
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get_by_oauth", return_value=None)
        mocker.patch("app.api.endpoints.auth.crud_user.get_by_email", return_value=mock_user)

        resp = client.get("/api/v1/auth/oauth/callback?provider=google&code=code&state=validstate")
        assert resp.status_code == 409

    def test_callback_inactive_user(self, client, mocker):
        mock_user = MagicMock()
        mock_user.oauth_provider = "google"
        mock_user.oauth_provider_id = "123"
        mock_user.is_active = False

        mocker.patch(
            "app.api.endpoints.auth.consume_oauth_state", return_value={"provider": "google"}
        )
        mocker.patch("app.auth.oauth2._get_client_credentials", return_value=("id", "secret"))
        mocker.patch("app.api.endpoints.auth.exchange_code", return_value={"access_token": "at"})
        mocker.patch(
            "app.api.endpoints.auth.get_user_info",
            return_value={"email": "inactive@example.com", "name": "Inactive", "id": "123"},
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get_by_oauth", return_value=mock_user)

        resp = client.get("/api/v1/auth/oauth/callback?provider=google&code=code&state=validstate")
        assert resp.status_code == 400

    def test_callback_no_email(self, client, mocker):
        mocker.patch(
            "app.api.endpoints.auth.consume_oauth_state", return_value={"provider": "google"}
        )
        mocker.patch("app.auth.oauth2._get_client_credentials", return_value=("id", "secret"))
        mocker.patch("app.api.endpoints.auth.exchange_code", return_value={"access_token": "at"})
        mocker.patch(
            "app.api.endpoints.auth.get_user_info", return_value={"name": "No Email", "id": "123"}
        )

        resp = client.get("/api/v1/auth/oauth/callback?provider=google&code=code&state=validstate")
        assert resp.status_code == 400
