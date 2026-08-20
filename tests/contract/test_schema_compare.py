"""Schema comparison test — detect breaking API changes against baseline.

This test compares the current OpenAPI schema against a stored baseline
to catch accidental breaking changes.

Run with:  poetry run pytest tests/contract/test_schema_compare.py
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-compare-secret-key-minimum-32-chars!!")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)
os.environ.setdefault(
    "DATABASE_URL_READER",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)

BASELINE_PATH = pathlib.Path("tests/contract/__snapshots__") / "openapi_baseline.json"


@pytest.mark.skipif(
    not BASELINE_PATH.exists(),
    reason="No baseline found. Run: poetry run python scripts/generate_openapi_baseline.py",
)
class TestSchemaComparison:
    def test_no_removed_endpoints(self, client) -> None:
        """Ensure no endpoints were removed since the baseline."""
        baseline = json.loads(BASELINE_PATH.read_text())
        current = client.get("/openapi.json").json()

        baseline_paths = set(baseline.get("paths", {}).keys())
        current_paths = set(current.get("paths", {}).keys())

        removed = baseline_paths - current_paths
        assert not removed, f"Endpoints removed since baseline: {removed}"

    def test_no_new_required_fields(self, client) -> None:
        """Check that no new required fields were added to existing schemas."""
        baseline = json.loads(BASELINE_PATH.read_text())
        current = client.get("/openapi.json").json()

        baseline_schemas = baseline.get("components", {}).get("schemas", {})
        current_schemas = current.get("components", {}).get("schemas", {})

        for name, schema in baseline_schemas.items():
            if name not in current_schemas:
                continue
            baseline_required = set(schema.get("required", []))
            current_required = set(current_schemas[name].get("required", []))
            # New required fields in existing schemas = breaking change
            new_required = current_required - baseline_required
            # Filter out fields that are new in the schema (OK) vs fields
            # added to previously existing schemas (breaking)
            baseline_props = set(schema.get("properties", {}).keys())
            truly_new_required = new_required & baseline_props
            assert not truly_new_required, (
                f"Breaking change in {name}: new required fields: {truly_new_required}"
            )

    def test_openapi_version_unchanged(self, client) -> None:
        """Ensure the OpenAPI version hasn't changed."""
        baseline = json.loads(BASELINE_PATH.read_text())
        current = client.get("/openapi.json").json()

        assert baseline.get("openapi") == current.get("openapi"), (
            "OpenAPI version changed — this is a breaking change"
        )
