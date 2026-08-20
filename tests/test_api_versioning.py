"""Tests for API versioning middleware, breaking change detection, and v2 infrastructure."""

import sys
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from app.main import app

sys.path.insert(0, str(Path("scripts")))
from check_api_breaking import find_breaking_changes


class TestVersioningMiddleware:
    def test_no_accept_header_returns_v1(self):
        with TestClient(app) as client:
            resp = client.get("/healthz")
            assert resp.headers.get("X-API-Version") == "1"

    def test_v1_explicit_accept_header(self):
        with TestClient(app) as client:
            resp = client.get(
                "/healthz",
                headers={"Accept": "application/vnd.app.v1+json"},
            )
            assert resp.headers.get("X-API-Version") == "1"

    def test_v2_accept_header(self):
        with TestClient(app) as client:
            resp = client.get(
                "/healthz",
                headers={"Accept": "application/vnd.app.v2+json"},
            )
            assert resp.headers.get("X-API-Version") == "2"


class TestBreakingChangeDetection:
    def test_no_changes(self):
        schema: dict[str, Any] = {
            "paths": {"/users": {"get": {}, "post": {}}},
            "components": {"schemas": {"User": {"properties": {"name": {"type": "string"}}}}},
        }
        result = find_breaking_changes(schema, schema)
        assert result == []

    def test_removed_endpoint(self):
        old: dict[str, Any] = {"paths": {"/users": {"get": {}}}}
        new: dict[str, Any] = {"paths": {}}
        result = find_breaking_changes(old, new)
        assert any("removed" in r.lower() for r in result)

    def test_removed_method(self):
        old: dict[str, Any] = {"paths": {"/users": {"get": {}, "post": {}}}}
        new: dict[str, Any] = {"paths": {"/users": {"get": {}}}}
        result = find_breaking_changes(old, new)
        assert any("method removed" in r.lower() for r in result)

    def test_new_required_property(self):
        old: dict[str, Any] = {
            "paths": {},
            "components": {"schemas": {"User": {"properties": {"name": {}}}}},
        }
        new: dict[str, Any] = {
            "paths": {},
            "components": {"schemas": {"User": {"properties": {"name": {}, "email": {}}, "required": ["email"]}}},
        }
        result = find_breaking_changes(old, new)
        assert any("required" in r.lower() and "added" in r.lower() for r in result)

    def test_removed_required_property(self):
        old: dict[str, Any] = {
            "paths": {},
            "components": {"schemas": {"User": {"properties": {"name": {}, "email": {}}, "required": ["email"]}}},
        }
        new: dict[str, Any] = {
            "paths": {},
            "components": {"schemas": {"User": {"properties": {"name": {}}}}},
        }
        result = find_breaking_changes(old, new)
        assert any("removed" in r.lower() for r in result)

    def test_added_optional_endpoint_not_breaking(self):
        old: dict[str, Any] = {"paths": {"/users": {"get": {}}}}
        new: dict[str, Any] = {"paths": {"/users": {"get": {}}, "/posts": {"get": {}}}}
        result = find_breaking_changes(old, new)
        assert result == []


class TestV2Router:
    def test_v2_router_exists(self):
        from app.api.v2 import api_v2_router

        assert api_v2_router is not None


class TestCLICommands:
    def test_update_baseline_command(self):
        from typer.testing import CliRunner

        from app.cli import app as cli_app

        runner = CliRunner()
        result = runner.invoke(cli_app, ["update-baseline", "--help"])
        assert result.exit_code == 0
        assert "baseline" in result.output.lower()

    def test_check_breaking_command(self):
        from typer.testing import CliRunner

        from app.cli import app as cli_app

        runner = CliRunner()
        result = runner.invoke(cli_app, ["check-breaking", "--help"])
        assert result.exit_code == 0
        assert "breaking" in result.output.lower()


class TestConfigDerivedURLs:
    def test_oauth_redirect_defaults_to_v1(self):
        from app.core.config import settings

        assert "/api/v1/auth/oauth/callback" in settings.OAUTH_REDIRECT_URL

    def test_csp_report_defaults_to_v1(self):
        from app.core.config import settings

        assert settings.CSP_REPORT_URI == "/api/v1/csp-report"
