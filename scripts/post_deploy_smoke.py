#!/usr/bin/env python3
"""Post-deploy smoke test suite.

Hits critical endpoints in sequence and reports pass/fail with timing.
Exit code 0 = all pass, 1 = any failure.

Usage:
  BASE_URL=https://app.example.com python scripts/post_deploy_smoke.py
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


@dataclass
class StepResult:
    name: str
    passed: bool
    status_code: int | None
    duration_ms: float
    error: str | None = None


async def run_smoke(base_url: str) -> list[StepResult]:
    """Run all smoke test steps against the given base URL."""
    results: list[StepResult] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0, follow_redirects=True) as client:
        # 1. Health check (liveness)
        t0 = time.monotonic()
        try:
            resp = await client.get("/healthz")
            passed = resp.status_code == 200
            results.append(
                StepResult("healthz", passed, resp.status_code, (time.monotonic() - t0) * 1000)
            )
        except Exception as e:
            results.append(
                StepResult("healthz", False, None, (time.monotonic() - t0) * 1000, str(e))
            )

        # 2. Readiness check
        t0 = time.monotonic()
        try:
            resp = await client.get("/readyz")
            passed = resp.status_code == 200
            results.append(
                StepResult("readyz", passed, resp.status_code, (time.monotonic() - t0) * 1000)
            )
        except Exception as e:
            results.append(
                StepResult("readyz", False, None, (time.monotonic() - t0) * 1000, str(e))
            )

        # 3. Register a user
        uid = f"smoke-{int(time.time())}"
        t0 = time.monotonic()
        try:
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"{uid}@test.example.com",
                    "username": uid,
                    "password": "SmokeTest1!",
                },
            )
            passed = resp.status_code in (201, 409)
            results.append(
                StepResult("register", passed, resp.status_code, (time.monotonic() - t0) * 1000)
            )
        except Exception as e:
            results.append(
                StepResult("register", False, None, (time.monotonic() - t0) * 1000, str(e))
            )

        # 4. Login
        t0 = time.monotonic()
        try:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"email": f"{uid}@test.example.com", "password": "SmokeTest1!"},
            )
            passed = resp.status_code == 200
            token: str | None = None
            if passed:
                data = resp.json()
                token = data.get("access_token")
            results.append(
                StepResult("login", passed, resp.status_code, (time.monotonic() - t0) * 1000)
            )
        except Exception as e:
            results.append(StepResult("login", False, None, (time.monotonic() - t0) * 1000, str(e)))
            token = None

        # 5. Authenticated request (list notifications)
        if token:
            t0 = time.monotonic()
            try:
                resp = await client.get(
                    "/api/v1/notifications/",
                    headers={"Authorization": f"Bearer {token}"},
                )
                passed = resp.status_code == 200
                results.append(
                    StepResult(
                        "notifications_list",
                        passed,
                        resp.status_code,
                        (time.monotonic() - t0) * 1000,
                    )
                )
            except Exception as e:
                results.append(
                    StepResult(
                        "notifications_list", False, None, (time.monotonic() - t0) * 1000, str(e)
                    )
                )

        # 6. Unauthenticated access returns 401
        t0 = time.monotonic()
        try:
            resp = await client.get("/api/v1/users/")
            passed = resp.status_code == 401
            results.append(
                StepResult(
                    "auth_required", passed, resp.status_code, (time.monotonic() - t0) * 1000
                )
            )
        except Exception as e:
            results.append(
                StepResult("auth_required", False, None, (time.monotonic() - t0) * 1000, str(e))
            )

        # 7. Dependencies check
        t0 = time.monotonic()
        try:
            resp = await client.get("/health/dependencies")
            passed = resp.status_code == 200
            results.append(
                StepResult("dependencies", passed, resp.status_code, (time.monotonic() - t0) * 1000)
            )
        except Exception as e:
            results.append(
                StepResult("dependencies", False, None, (time.monotonic() - t0) * 1000, str(e))
            )

    return results


def print_report(results: list[StepResult]) -> None:
    """Print a human-readable report."""
    all_passed = True
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        if not r.passed:
            all_passed = False
        http = f" (HTTP {r.status_code})" if r.status_code is not None else ""
        err = f" - {r.error}" if r.error else ""
        print(f"  [{status}] {r.name}{http} ({r.duration_ms:.0f}ms){err}")

    print()
    if all_passed:
        print("All smoke tests passed.")
    else:
        print("Smoke tests FAILED.")
        failed = [r.name for r in results if not r.passed]
        print(f"Failed steps: {', '.join(failed)}")


def main() -> None:
    base_url = BASE_URL
    print(f"Running post-deploy smoke tests against {base_url}...")
    print()
    results = asyncio.run(run_smoke(base_url))
    print_report(results)

    # Write JSON for CI artifact consumption
    output = [
        {
            "name": r.name,
            "passed": r.passed,
            "status_code": r.status_code,
            "duration_ms": round(r.duration_ms, 1),
            "error": r.error,
        }
        for r in results
    ]
    from pathlib import Path

    Path("smoke-results.json").write_text(json.dumps(output, indent=2))

    if not all(r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
