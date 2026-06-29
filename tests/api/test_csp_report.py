import pytest
from httpx import AsyncClient


class TestCSPReportEndpoint:
    @pytest.mark.asyncio
    async def test_csp_report_accepted(self, async_client: AsyncClient):
        report = {
            "csp-report": {
                "document-uri": "https://example.com/page",
                "violated-directive": "script-src-elem",
                "effective-directive": "script-src-elem",
                "original-policy": "default-src 'self'",
                "blocked-uri": "https://evil.com/hack.js",
                "source-file": "https://example.com/page",
                "line-number": 42,
                "column-number": 10,
            }
        }
        response = await async_client.post("/api/v1/csp-report", json=report)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_csp_report_empty_body(self, async_client: AsyncClient):
        response = await async_client.post("/api/v1/csp-report", json={})
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_csp_report_invalid_json(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/csp-report",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_csp_report_not_found(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/csp-report")
        assert response.status_code == 405

    @pytest.mark.asyncio
    async def test_security_headers_includes_report_uri(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/auth/login")
        csp = response.headers.get("content-security-policy", "")
        assert "report-uri /api/v1/csp-report" in csp
        report_to = response.headers.get("report-to", "")
        assert "csp-endpoint" in report_to
