#!/usr/bin/env python3
"""Check for breaking API changes using OpenAPI schema comparison.

Compares the current schema against a stored baseline.
Exit 0 for non-breaking, exit 1 for breaking changes.

Usage:
  python scripts/check_api_breaking.py [--baseline openapi-baseline.json]
"""

import json
import sys
from pathlib import Path

BASELINE_PATH = Path("openapi-baseline.json")


def _flatten_schema(schema: dict, prefix: str = "") -> dict[str, set[str]]:
    """Flatten OpenAPI schema into {path: {methods}} for comparison."""
    endpoints: dict[str, set[str]] = {}
    paths = schema.get("paths", {})
    for path, methods in paths.items():
        for method in methods:
            if method in ("get", "post", "put", "patch", "delete", "head", "options"):
                full_path = f"{prefix}{path}" if prefix else path
                if full_path not in endpoints:
                    endpoints[full_path] = set()
                endpoints[full_path].add(method)
    return endpoints


def _flatten_schemas(schema: dict) -> dict[str, dict]:
    """Extract component schemas."""
    return schema.get("components", {}).get("schemas", {})


def find_breaking_changes(old: dict, new: dict) -> list[str]:
    """Compare two OpenAPI schemas and return breaking changes."""
    breaking: list[str] = []

    old_endpoints = _flatten_schema(old)
    new_endpoints = _flatten_schema(new)

    # Removed endpoints
    for path, methods in old_endpoints.items():
        if path not in new_endpoints:
            breaking.append(f"Endpoint removed: {path}")
        else:
            for method in methods:
                if method not in new_endpoints[path]:
                    breaking.append(f"Method removed: {method.upper()} {path}")

    # Removed required schema properties
    old_schemas = _flatten_schemas(old)
    new_schemas = _flatten_schemas(new)
    for name, schema in old_schemas.items():
        if name not in new_schemas:
            breaking.append(f"Schema removed: {name}")
            continue
        old_required = set(schema.get("required", []))
        new_required = set(new_schemas[name].get("required", []))
        new_props = set(new_schemas[name].get("properties", {}).keys())
        # A property that was optional in old schema but removed entirely from new schema
        old_props = set(schema.get("properties", {}).keys())
        for prop in old_props - new_props:
            if prop in old_required:
                breaking.append(f"Required property removed: {name}.{prop}")

    # Added required properties (backward-incompatible)
    for name, schema in new_schemas.items():
        if name not in old_schemas:
            continue
        new_required = set(schema.get("required", []))
        old_required = set(old_schemas[name].get("required", []))
        for prop in new_required - old_required:
            breaking.append(f"New required property added: {name}.{prop}")

    return breaking


def main() -> None:
    baseline_path = BASELINE_PATH
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--baseline" and i < len(sys.argv) - 1:
            baseline_path = Path(sys.argv[i + 1])

    if not baseline_path.exists():
        print(f"Baseline not found at {baseline_path}. Skipping breaking change check.")
        sys.exit(0)

    baseline = json.loads(baseline_path.read_text())

    # Read current schema from file or generate
    current_path = Path("openapi-current.json")
    if current_path.exists():
        current = json.loads(current_path.read_text())
    else:
        print("No openapi-current.json found. Run the app and save /openapi.json first.")
        print("Alternatively: curl http://localhost:8000/openapi.json > openapi-current.json")
        sys.exit(0)

    breaking = find_breaking_changes(baseline, current)

    if breaking:
        print("BREAKING CHANGES DETECTED:")
        for change in breaking:
            print(f"  - {change}")
        sys.exit(1)
    else:
        print("No breaking changes detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
