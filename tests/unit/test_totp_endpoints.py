"""Tests for TOTP 2FA endpoints and login flow."""

from unittest.mock import AsyncMock


class TestTOTPStatusEndpoint:
    def test_status_returns_disabled_when_not_configured(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = False
        mock_user.totp_verified_at = None

        async def _fake_user():
            return mock_user

        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        try:
            resp = client.get("/api/v1/auth/totp/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["enabled"] is False
            assert data["totp_verified_at"] is None
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_status_returns_enabled_when_active(self, client, mocker):
        from datetime import UTC, datetime

        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = True
        mock_user.totp_verified_at = datetime.now(UTC)

        async def _fake_user():
            return mock_user

        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        try:
            resp = client.get("/api/v1/auth/totp/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["enabled"] is True
            assert data["totp_verified_at"] is not None
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestTOTPEnableEndpoint:
    def test_enable_requires_auth(self, client):
        resp = client.post("/api/v1/auth/totp/enable")
        assert resp.status_code == 401

    def test_enable_returns_secret_and_uri(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = False
        mock_user.email = "test@example.com"
        mock_user.id = 1
        mock_user.tenant_id = 1

        async def _fake_user():
            return mock_user

        async def _fake_db():
            return AsyncMock()

        from app.api.deps import get_current_user, get_db
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_db] = _fake_db
        try:
            resp = client.post("/api/v1/auth/totp/enable")
            assert resp.status_code == 200
            data = resp.json()
            assert "secret" in data
            assert len(data["secret"]) == 40
            assert "uri" in data
            assert data["uri"].startswith("otpauth://")
            assert "backup_codes" in data
            assert len(data["backup_codes"]) > 0
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_enable_when_already_enabled(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = True

        async def _fake_user():
            return mock_user

        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        try:
            resp = client.post("/api/v1/auth/totp/enable")
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestTOTPVerifyEnableEndpoint:
    def test_verify_requires_auth(self, client):
        resp = client.post("/api/v1/auth/totp/verify-enable", json={"code": "123456"})
        assert resp.status_code == 401

    def test_verify_with_invalid_code(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = False
        mock_user.totp_secret = "test-secret"
        mock_user.id = 1
        mock_user.tenant_id = 1

        async def _fake_user():
            return mock_user

        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        mocker.patch("app.api.endpoints.totp.verify_totp_code", return_value=False)
        try:
            resp = client.post("/api/v1/auth/totp/verify-enable", json={"code": "123456"})
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_verify_with_valid_code(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = False
        mock_user.totp_secret = "test-secret"
        mock_user.id = 1
        mock_user.tenant_id = 1

        async def _fake_user():
            return mock_user

        async def _fake_db():
            return AsyncMock()

        from app.api.deps import get_current_user, get_db
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_db] = _fake_db
        mocker.patch("app.api.endpoints.totp.verify_totp_code", return_value=True)
        try:
            resp = client.post("/api/v1/auth/totp/verify-enable", json={"code": "123456"})
            assert resp.status_code == 200
            assert resp.json()["detail"] == "TOTP 2FA enabled successfully"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_verify_when_already_enabled(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = True

        async def _fake_user():
            return mock_user

        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        try:
            resp = client.post("/api/v1/auth/totp/verify-enable", json={"code": "123456"})
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_verify_without_pending_setup(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = False
        mock_user.totp_secret = None

        async def _fake_user():
            return mock_user

        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        try:
            resp = client.post("/api/v1/auth/totp/verify-enable", json={"code": "123456"})
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestTOTPDisableEndpoint:
    def test_disable_requires_auth(self, client):
        resp = client.post("/api/v1/auth/totp/disable", json={"password": "secret"})
        assert resp.status_code == 401

    def test_disable_with_wrong_password(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = True
        mock_user.hashed_password = "hashed"
        mock_user.id = 1
        mock_user.tenant_id = 1

        async def _fake_user():
            return mock_user

        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        mocker.patch("app.api.endpoints.totp.verify_password", return_value=False)
        try:
            resp = client.post("/api/v1/auth/totp/disable", json={"password": "wrong"})
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_disable_success(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = True
        mock_user.hashed_password = "hashed"
        mock_user.id = 1
        mock_user.tenant_id = 1

        async def _fake_user():
            return mock_user

        async def _fake_db():
            return AsyncMock()

        from app.api.deps import get_current_user, get_db
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_db] = _fake_db
        mocker.patch("app.api.endpoints.totp.verify_password", return_value=True)
        try:
            resp = client.post("/api/v1/auth/totp/disable", json={"password": "correct"})
            assert resp.status_code == 200
            assert resp.json()["detail"] == "TOTP 2FA disabled successfully"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_disable_when_not_enabled(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.totp_enabled = False

        async def _fake_user():
            return mock_user

        from app.api.deps import get_current_user
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        try:
            resp = client.post("/api/v1/auth/totp/disable", json={"password": "test"})
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestTOTPLoginFlow:
    def test_login_returns_challenge_when_totp_enabled(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.id = 1
        mock_user.totp_enabled = True
        mock_user.email = "test@example.com"
        mock_user.totp_secret = "secret"

        mocker.patch("app.api.endpoints.auth.authenticate_user", return_value=mock_user)
        mocker.patch(
            "app.api.endpoints.auth.create_totp_challenge_token", return_value="challenge-token"
        )

        resp = client.post(
            "/api/v1/auth/login", data={"username": "test@example.com", "password": "password"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["totp_required"] is True
        assert data["challenge_token"] == "challenge-token"
        assert data["token_type"] == "totp_challenge"

    def test_login_returns_tokens_when_totp_disabled(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.id = 1
        mock_user.totp_enabled = False
        mock_user.email = "test@example.com"

        mocker.patch("app.api.endpoints.auth.authenticate_user", return_value=mock_user)
        mocker.patch(
            "app.api.endpoints.auth._issue_tokens",
            return_value={"access_token": "at", "refresh_token": "rt", "token_type": "bearer"},
        )

        resp = client.post(
            "/api/v1/auth/login", data={"username": "test@example.com", "password": "password"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "at"
        assert data["token_type"] == "bearer"

    def test_totp_verify_invalid_challenge_token(self, client):
        """Without auth — the endpoint uses challenge token, not bearer token,
        so invalid challenge yields 400, not 401."""
        resp = client.post(
            "/api/v1/auth/login/totp-verify",
            json={"challenge_token": "tok", "code": "123456"},
        )
        assert resp.status_code == 400

    def test_totp_verify_invalid_challenge(self, client, mocker):
        from fastapi import HTTPException

        mocker.patch(
            "app.api.endpoints.auth.decode_totp_challenge_token",
            side_effect=HTTPException(status_code=400, detail="bad token"),
        )

        resp = client.post(
            "/api/v1/auth/login/totp-verify",
            json={"challenge_token": "bad", "code": "123456"},
        )
        assert resp.status_code == 400

    def test_totp_verify_valid_code(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.id = 1
        mock_user.is_active = True
        mock_user.totp_enabled = True
        mock_user.totp_secret = "secret"
        mock_user.backup_codes = None

        mocker.patch(
            "app.api.endpoints.auth.decode_totp_challenge_token", return_value={"sub": "1"}
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get", return_value=mock_user)
        mocker.patch("app.api.endpoints.auth.verify_totp_code", return_value=True)
        mocker.patch(
            "app.api.endpoints.auth._issue_tokens",
            return_value={"access_token": "at", "refresh_token": "rt", "token_type": "bearer"},
        )

        resp = client.post(
            "/api/v1/auth/login/totp-verify",
            json={"challenge_token": "tok", "code": "123456"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "at"

    def test_totp_verify_with_backup_code(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.id = 1
        mock_user.is_active = True
        mock_user.totp_enabled = True
        mock_user.totp_secret = "secret"
        mock_user.backup_codes = "hash1,hash2,hash3"

        async def _fake_db():
            return AsyncMock()

        from app.api.deps import get_db

        mocker.patch(
            "app.api.endpoints.auth.decode_totp_challenge_token", return_value={"sub": "1"}
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get", return_value=mock_user)
        mocker.patch("app.api.endpoints.auth.verify_totp_code", return_value=False)
        mocker.patch("app.api.endpoints.auth.verify_backup_code", return_value="hash2")
        mocker.patch("app.api.endpoints.auth.remove_used_backup_code", return_value="hash1,hash3")
        mocker.patch(
            "app.api.endpoints.auth._issue_tokens",
            return_value={"access_token": "at", "refresh_token": "rt", "token_type": "bearer"},
        )

        from app.main import app

        app.dependency_overrides[get_db] = _fake_db
        try:
            resp = client.post(
                "/api/v1/auth/login/totp-verify",
                json={"challenge_token": "tok", "code": "BC0001"},
            )
            assert resp.status_code == 200
            assert mock_user.backup_codes == "hash1,hash3"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_totp_verify_invalid_code(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.id = 1
        mock_user.is_active = True
        mock_user.totp_enabled = True
        mock_user.totp_secret = "secret"
        mock_user.backup_codes = None

        mocker.patch(
            "app.api.endpoints.auth.decode_totp_challenge_token", return_value={"sub": "1"}
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get", return_value=mock_user)
        mocker.patch("app.api.endpoints.auth.verify_totp_code", return_value=False)
        mocker.patch("app.api.endpoints.auth.verify_backup_code", return_value=None)

        resp = client.post(
            "/api/v1/auth/login/totp-verify",
            json={"challenge_token": "tok", "code": "000000"},
        )
        assert resp.status_code == 400

    def test_totp_verify_user_not_found(self, client, mocker):
        mocker.patch(
            "app.api.endpoints.auth.decode_totp_challenge_token", return_value={"sub": "999"}
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get", return_value=None)

        resp = client.post(
            "/api/v1/auth/login/totp-verify",
            json={"challenge_token": "tok", "code": "123456"},
        )
        assert resp.status_code == 400

    def test_totp_verify_totp_not_enabled(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.id = 1
        mock_user.is_active = True
        mock_user.totp_enabled = False
        mock_user.totp_secret = None

        mocker.patch(
            "app.api.endpoints.auth.decode_totp_challenge_token", return_value={"sub": "1"}
        )
        mocker.patch("app.api.endpoints.auth.crud_user.get", return_value=mock_user)

        resp = client.post(
            "/api/v1/auth/login/totp-verify",
            json={"challenge_token": "tok", "code": "123456"},
        )
        assert resp.status_code == 400
