"""Fixtures for Playwright E2E tests against the admin dashboard.

The admin panel uses JWT Bearer auth (no login form).  We inject the
Authorization header into every request via ``page.route()`` so the
server sees a valid token without needing a browser-based login flow.
"""

from __future__ import annotations

import multiprocessing
import os
import socket
import time
from collections.abc import Generator

import pytest

# Force test env before any app import
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "e2e-test-secret-key-minimum-32-chars!!")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)
os.environ.setdefault(
    "DATABASE_URL_READER",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
)


def _run_server(port: int) -> None:
    """Start uvicorn in a subprocess (isolated event loop)."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        timeout_graceful_shutdown=5,
    )


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def e2e_base_url() -> Generator[str, None, None]:
    """Start the app server once for the entire session."""
    port = _find_free_port()
    proc = multiprocessing.Process(target=_run_server, args=(port,), daemon=True)
    proc.start()

    # Wait for the server to become responsive
    import httpx

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=2)
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            pass
        time.sleep(0.5)
    else:
        proc.terminate()
        pytest.skip("E2E server failed to start within 30 s")

    yield f"http://127.0.0.1:{port}"

    proc.terminate()
    proc.join(timeout=5)


@pytest.fixture(scope="session")
def admin_jwt_token() -> str:
    """Create a valid JWT for a superuser (id=1) without touching the DB."""
    from app.core.security import create_access_token

    return create_access_token(subject="1")


@pytest.fixture()
def e2e_context(
    playwright: object,
    browser: object,
    e2e_base_url: str,
    admin_jwt_token: str,
) -> Generator[object, None, None]:
    """Provide a BrowserContext with JWT auth header injected on every request."""
    context = browser.new_context(base_url=e2e_base_url)

    # Inject Authorization header on every request
    def _route_handler(route: object) -> None:
        headers = {**route.request.headers, "Authorization": f"Bearer {admin_jwt_token}"}  # type: ignore[attr-defined]
        route.continue_(headers=headers)  # type: ignore[attr-defined]

    context.route("**/*", _route_handler)
    yield context
    context.close()


@pytest.fixture()
def e2e_page(e2e_context: object) -> Generator[object, None, None]:
    """Provide a Page pre-configured with admin JWT auth."""
    page = e2e_context.new_page()  # type: ignore[attr-defined]
    yield page
    page.close()
