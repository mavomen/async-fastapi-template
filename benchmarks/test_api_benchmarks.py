"""pytest-benchmark tests for critical API endpoints."""

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
    result = benchmark(
        lambda: client.post(
            "/api/v1/auth/register",
            json={"email": "bench@example.com", "username": "benchuser", "password": "BenchPass1!"},
        )
    )
    assert result.status_code == 201
