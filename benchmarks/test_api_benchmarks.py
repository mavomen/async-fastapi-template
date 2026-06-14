"""pytest-benchmark tests for critical API endpoints."""

from itertools import count

from fastapi.testclient import TestClient


def test_health_endpoint(benchmark, client: TestClient):
    """Benchmark the health endpoint."""
    result = benchmark(lambda: client.get("/health"))
    assert result.status_code == 200


def test_users_list_endpoint(benchmark, client: TestClient):
    """Benchmark the users list endpoint (requires auth, will test response time of 403)."""
    # Without auth, we still measure response time of permission check
    result = benchmark(lambda: client.get("/api/v1/users/"))
    assert result.status_code == 401  # unauthorized, but fast response


def test_register_endpoint(benchmark, client: TestClient):
    """Benchmark the register endpoint."""
    _counter = count()

    def _register():
        i = next(_counter)
        return client.post(
            "/api/v1/auth/register",
            json={
                "email": f"bench-{i}@example.com",
                "username": f"benchuser-{i}",
                "password": "BenchPass1!",
            },
        )

    result = benchmark(_register)
    assert result.status_code == 201
