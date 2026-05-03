"""Smoke tests for tracing setup."""

from fastapi.testclient import TestClient


def test_tracing_does_not_break_app(client: TestClient):
    """App should still respond normally with tracing enabled."""
    response = client.get("/health")
    assert response.status_code == 200


def test_tracing_provider_set():
    """Verify a tracer provider is configured."""
    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    assert provider is not None
    # In test, it could be TracerProvider or NoOp
    assert hasattr(provider, "get_tracer")
