"""Script to regenerate the OpenAPI baseline snapshot.

Run with:  poetry run python scripts/generate_openapi_baseline.py
"""

from __future__ import annotations

import json
import os
import pathlib

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-baseline-secret-key-minimum-32-chars!!")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)
os.environ.setdefault(
    "DATABASE_URL_READER",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)

BASELINE_PATH = pathlib.Path("tests/contract/__snapshots__") / "openapi_baseline.json"
BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    from app.main import app

    schema = app.openapi()
    BASELINE_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"OpenAPI baseline written to {BASELINE_PATH}")
    print(f"  version: {schema.get('openapi', 'unknown')}")
    print(f"  paths: {len(schema.get('paths', {}))}")


if __name__ == "__main__":
    main()
