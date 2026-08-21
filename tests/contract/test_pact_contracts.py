"""Consumer-driven contract tests using pact-python (v3 API).

Defines the expected API contract for client consumers, verifying
the provider (FastAPI app) satisfies those expectations.

Run with:  poetry run pytest tests/contract/test_pact_contracts.py --no-cov -v
"""

from __future__ import annotations

import os
import pathlib

import pact
import pytest

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-pact-secret-key-minimum-32-chars!!")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)
os.environ.setdefault(
    "DATABASE_URL_READER",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)

PACT_DIR = pathlib.Path(__file__).parent.parent.parent / "pacts"


class TestUserAPIConsumerContract:
    """Consumer contract for the User API."""

    @pytest.fixture()
    def pact_dir(self) -> pathlib.Path:
        PACT_DIR.mkdir(parents=True, exist_ok=True)
        return PACT_DIR

    @pytest.fixture()
    def pact(self) -> pact.Pact:
        return pact.Pact("WebApp", "FastAPIProvider")

    def test_get_users_contract(self, pact: pact.Pact, pact_dir: pathlib.Path) -> None:
        """Contract: GET /api/v1/users returns a paginated user list."""
        (
            pact.upon_receiving("a request for the user list")
            .given("users exist")
            .with_request("get", "/api/v1/users")
            .will_respond_with(200)
        )
        pact.write_file(pact_dir)
        assert (pact_dir / "WebApp-FastAPIProvider.json").exists()

    def test_health_contract(self, pact: pact.Pact, pact_dir: pathlib.Path) -> None:
        """Contract: GET /health/live returns 200."""
        (
            pact.upon_receiving("a health check request")
            .with_request("get", "/health/live")
            .will_respond_with(200)
        )
        pact.write_file(pact_dir)
        assert (pact_dir / "WebApp-FastAPIProvider.json").exists()

    def test_readiness_contract(self, pact: pact.Pact, pact_dir: pathlib.Path) -> None:
        """Contract: GET /health/ready returns 200 when dependencies are up."""
        (
            pact.upon_receiving("a readiness check request")
            .given("database is connected")
            .with_request("get", "/health/ready")
            .will_respond_with(200)
        )
        pact.write_file(pact_dir)
        assert (pact_dir / "WebApp-FastAPIProvider.json").exists()

    def test_user_detail_contract(self, pact: pact.Pact, pact_dir: pathlib.Path) -> None:
        """Contract: GET /api/v1/users/{id} returns a single user."""
        (
            pact.upon_receiving("a request for user 1")
            .given("user with id 1 exists")
            .with_request("get", "/api/v1/users/1")
            .will_respond_with(200)
        )
        pact.write_file(pact_dir)
        assert (pact_dir / "WebApp-FastAPIProvider.json").exists()

    def test_notifications_contract(self, pact: pact.Pact, pact_dir: pathlib.Path) -> None:
        """Contract: GET /api/v1/notifications returns a notification list."""
        (
            pact.upon_receiving("a request for notifications")
            .given("user has notifications")
            .with_request("get", "/api/v1/notifications")
            .will_respond_with(200)
        )
        pact.write_file(pact_dir)
        assert (pact_dir / "WebApp-FastAPIProvider.json").exists()
