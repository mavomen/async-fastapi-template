"""OpenAPI schema snapshot test using syrupy."""

from fastapi.testclient import TestClient


def test_openapi_schema_snapshot(client: TestClient, snapshot):
    """Verify the OpenAPI schema hasn't changed unexpectedly."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    # Compare against stored snapshot (update with --snapshot-update)
    assert response.json() == snapshot(name="openapi_schema")
