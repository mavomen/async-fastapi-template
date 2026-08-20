#!/usr/bin/env python3
"""Regenerate the OpenAPI baseline snapshot from the current schema.

Usage:
  python scripts/update_openapi_baseline.py
"""

import json
import sys
from pathlib import Path

BASELINE_PATH = Path("openapi-baseline.json")


def main() -> None:
    """Start the app briefly, fetch the schema, and save as baseline."""
    print("Generating OpenAPI baseline...")

    # Use the app's test client to get the schema without starting a server
    try:
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/openapi.json")
            if resp.status_code != 200:
                print(f"Failed to get OpenAPI schema: HTTP {resp.status_code}")
                sys.exit(1)
            schema = resp.json()
    except Exception as e:
        print(f"Could not generate schema: {e}")
        sys.exit(1)

    BASELINE_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True))
    print(f"Baseline written to {BASELINE_PATH}")


if __name__ == "__main__":
    main()
