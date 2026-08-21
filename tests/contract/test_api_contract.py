"""Contract and fuzz tests for the FastAPI API.

Full endpoint fuzzing runs in CI via ``schemathesis run --experimental=openapi-3.1``.
These pytest-based tests validate schema generation, endpoint availability,
and generate random payloads for key endpoints via Hypothesis.

Run with:  poetry run pytest tests/contract/test_api_contract.py --no-cov
"""

from __future__ import annotations

import os

import hypothesis
from hypothesis import given, settings
from hypothesis import strategies as st

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-fuzz-secret-key-minimum-32-chars!!")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)
os.environ.setdefault(
    "DATABASE_URL_READER",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)

from app.main import app


class TestOpenAPISchema:
    """Validate the generated OpenAPI schema is well-formed."""

    def test_openapi_version(self) -> None:
        schema = app.openapi()
        assert schema["openapi"].startswith("3.")

    def test_all_paths_present(self) -> None:
        schema = app.openapi()
        assert len(schema.get("paths", {})) > 0

    def test_all_schemas_have_required_fields(self) -> None:
        schema = app.openapi()
        for name, definition in schema.get("components", {}).get("schemas", {}).items():
            assert "properties" in definition or "oneOf" in definition or "anyOf" in definition, (
                f"Schema {name} has no properties, oneOf, or anyOf"
            )

    def test_no_ref_leaks(self) -> None:
        """No dangling $ref that points to non-existent schema."""
        import json
        import re

        schema = app.openapi()
        raw = json.dumps(schema)
        refs = re.findall(r'\$ref": "#/components/schemas/([^"]+)"', raw)
        schemas = set(schema.get("components", {}).get("schemas", {}).keys())
        for ref in refs:
            assert ref in schemas, f"Dangling $ref: {ref}"

    def test_security_schemes_defined(self) -> None:
        schema = app.openapi()
        sec = schema.get("components", {}).get("securitySchemes", {})
        assert len(sec) > 0, "No security schemes defined"


class TestEndpointAvailability:
    """Verify all expected endpoints are registered."""

    EXPECTED_PREFIXES = [
        "/api/v1/",
        "/health/",
        "/admin",
        "/profile",
    ]

    def test_expected_prefixes_registered(self) -> None:
        schema = app.openapi()
        paths = set(schema.get("paths", {}).keys())
        for prefix in self.EXPECTED_PREFIXES:
            matching = [p for p in paths if p.startswith(prefix)]
            assert len(matching) > 0, f"No endpoints found for prefix {prefix}"

    def test_healthz_and_readyz_not_in_openapi(self) -> None:
        """K8s probe endpoints are intentionally excluded from OpenAPI."""
        schema = app.openapi()
        paths = set(schema.get("paths", {}).keys())
        assert "/healthz" not in paths
        assert "/readyz" not in paths


class TestEndpointFuzz:
    """Generate random payloads for key endpoints.

    Live fuzzing against the running server runs in CI via:
        schemathesis run http://localhost:8000/openapi.json \\
            --experimental=openapi-3.1 --checks all --hypothesis-max-examples=50
    """

    @given(
        email=st.emails(),
        username=st.from_regex(r"[a-zA-Z0-9_-]{3,50}", fullmatch=True),
        password=st.text(min_size=8, max_size=100).filter(lambda p: len(p) >= 8),
    )
    @settings(
        max_examples=50, suppress_health_check=list(hypothesis.settings().suppress_health_check)
    )
    def test_user_create_payloads(self, email: str, username: str, password: str) -> None:
        """Generate valid user creation payloads."""
        from app.schemas.user import UserCreate

        user = UserCreate(email=email, username=username, password=password)
        data = user.model_dump()
        assert "email" in data
        assert "username" in data
        assert "password" in data

    @given(
        email=st.emails() | st.none(),
        full_name=st.text(max_size=100) | st.none(),
        is_active=st.booleans() | st.none(),
    )
    @settings(max_examples=50)
    def test_user_update_payloads(
        self, email: str | None, full_name: str | None, is_active: bool | None
    ) -> None:
        """Generate valid user update payloads."""
        from app.schemas.user import UserUpdate

        update = UserUpdate(email=email, full_name=full_name, is_active=is_active)
        data = update.model_dump(exclude_unset=True)
        assert len(data) > 0 or (email is None and full_name is None and is_active is None)

    @given(
        path_suffix=st.sampled_from(
            [
                "users",
                "tenants",
                "webhooks",
                "notifications",
            ]
        )
    )
    @settings(max_examples=5)
    def test_api_v1_endpoints_exist(self, path_suffix: str) -> None:
        """All expected API v1 sub-paths exist in the schema."""
        schema = app.openapi()
        paths = schema.get("paths", {})
        matching = [p for p in paths if f"/api/v1/{path_suffix}" in p]
        assert len(matching) > 0, f"No endpoints found matching /api/v1/{path_suffix}"

    @given(data=st.binary(min_size=0, max_size=1024))
    @settings(max_examples=30)
    def test_invalid_body_rejected(self, data: bytes) -> None:
        """Sending random binary data should never cause a 500."""
        from fastapi.testclient import TestClient

        with TestClient(app=app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/auth/register",
                content=data,
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code in (400, 422, 415, 429), (
                f"Unexpected status {resp.status_code} for binary payload"
            )
