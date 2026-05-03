"""Tests for Prometheus metrics endpoint."""

from fastapi.testclient import TestClient


def test_metrics_endpoint_accessible(client: TestClient):
    """Metrics endpoint should return 200 and valid Prometheus text."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_metrics_include_custom_collectors(client: TestClient):
    """Custom database metrics appear in output after a DB request."""
    # Trigger a database usage (health/ready uses the DB)
    client.get("/health/ready")

    # Now the db_connections_total must be present in the metrics
    response = client.get("/metrics")
    assert "db_connections_total" in response.text
