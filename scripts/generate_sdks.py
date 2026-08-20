#!/usr/bin/env python3
"""Generate typed client SDKs from the OpenAPI schema.

Supports:
  - Python SDK via ``openapi-python-client``
  - TypeScript types via ``openapi-typescript`` (requires npx / npm)

Usage:
    python scripts/generate_sdks.py            # both Python + TS
    python scripts/generate_sdks.py --python   # Python only
    python scripts/generate_sdks.py --ts       # TypeScript only
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "docs" / "openapi.json"
PYTHON_SDK_DIR = ROOT / "sdk" / "python"
TS_SDK_DIR = ROOT / "sdk" / "typescript"
OPENAPI_CONFIG = ROOT / ".openapi-python-client.toml"


def _export_schema() -> None:
    """Export the OpenAPI schema from the running app or the schema file."""
    if SCHEMA_PATH.exists():
        print(f"Using existing schema: {SCHEMA_PATH}")
        return

    print("Exporting OpenAPI schema from app ...")
    try:
        result = subprocess.run(
            [sys.executable, "-c", "from app.main import app; print(json.dumps(app.openapi()))"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=True,
        )
        SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_PATH.write_text(result.stdout)
        print(f"Schema written to {SCHEMA_PATH}")
    except subprocess.CalledProcessError as exc:
        print(f"Failed to export schema: {exc.stderr}", file=sys.stderr)
        sys.exit(1)


def generate_python_sdk() -> None:
    """Generate a typed Python client via openapi-python-client."""
    print("\n--- Python SDK ---")
    _export_schema()

    # Clean previous output
    if PYTHON_SDK_DIR.exists():
        shutil.rmtree(PYTHON_SDK_DIR)
    PYTHON_SDK_DIR.mkdir(parents=True)

    # Run openapi-python-client using its config
    result = subprocess.run(
        [
            sys.executable, "-m", "openapi_python_client",
            "generate",
            f"--config-path={OPENAPI_CONFIG}",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT), check=False,
    )

    if result.returncode != 0:
        print(f"openapi-python-client failed:\n{result.stderr}", file=sys.stderr)
        # Try fallback: direct CLI invocation
        result2 = subprocess.run(
            ["poetry", "run", "openapi-python-client", "generate",
             f"--config-path={OPENAPI_CONFIG}"],
            capture_output=True,
            text=True,
            cwd=str(ROOT), check=False,
        )
        if result2.returncode != 0:
            print(f"Fallback also failed:\n{result2.stderr}", file=sys.stderr)
            sys.exit(1)

    print(f"Python SDK generated in {PYTHON_SDK_DIR}")
    _print_python_sdk_readme()


def _print_python_sdk_readme() -> None:
    readme = PYTHON_SDK_DIR / "README.md"
    if readme.exists():
        return
    readme.write_text(
        textwrap.dedent(f"""\
        # async-fastapi-template Python Client

        Auto-generated typed Python client for the FastAPI template API.

        ## Installation

        ```bash
        pip install {PYTHON_SDK_DIR}
        ```

        ## Usage

        ```python
        from async_fastapi_template_client import Client

        client = Client(base_url="http://localhost:8000")
        # client.users.get_current_user(...)
        ```
        """)
    )


def generate_typescript_sdk() -> None:
    """Generate TypeScript types via openapi-typescript (npx)."""
    print("\n--- TypeScript SDK ---")
    _export_schema()

    # Check if npx is available
    npx = shutil.which("npx")
    if npx is None:
        print("npx not found — skipping TypeScript SDK generation.")
        print("Install Node.js/npm to enable TypeScript generation.")
        return

    if TS_SDK_DIR.exists():
        shutil.rmtree(TS_SDK_DIR)
    TS_SDK_DIR.mkdir(parents=True)

    result = subprocess.run(
        [
            npx, "--yes", "openapi-typescript",
            str(SCHEMA_PATH),
            "-o", str(TS_SDK_DIR / "api.d.ts"),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT), check=False,
    )

    if result.returncode != 0:
        print(f"openapi-typescript failed:\n{result.stderr}", file=sys.stderr)
        return  # non-fatal — Python SDK is the primary target

    print(f"TypeScript types generated in {TS_SDK_DIR / 'api.d.ts'}")

    # Write a package.json for the SDK
    pkg = TS_SDK_DIR / "package.json"
    pkg.write_text(
        json.dumps(
            {
                "name": "async-fastapi-template-typescript-client",
                "version": "0.1.0",
                "description": "Auto-generated TypeScript types for the FastAPI template API",
                "main": "api.d.ts",
                "types": "api.d.ts",
                "license": "MIT",
            },
            indent=2,
        )
    )


def main() -> None:
    args = sys.argv[1:]
    do_python = "--python" not in args
    do_ts = "--ts" not in args

    if not do_python and not do_ts:
        do_python = do_ts = True

    if do_python:
        generate_python_sdk()
    if do_ts:
        generate_typescript_sdk()

    print("\nSDK generation complete.")


if __name__ == "__main__":
    main()
