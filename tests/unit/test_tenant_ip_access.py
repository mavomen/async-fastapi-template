"""Tests for TenantIPAccessMiddleware and IP rule matching."""

from unittest.mock import AsyncMock

import pytest
from fastapi import Request

from app.middleware.tenant_ip_access import _ip_matches_rule, _parse_forwarded_for


class TestIPRuleHelpers:
    def test_parse_forwarded_for_returns_first_ip(self):
        request = AsyncMock(spec=Request)
        request.headers = {"X-Forwarded-For": "203.0.113.5, 198.51.100.2"}
        request.client = None
        assert _parse_forwarded_for(request) == "203.0.113.5"

    def test_parse_forwarded_for_falls_back_to_client(self):
        request = AsyncMock(spec=Request)
        request.headers = {}
        request.client = AsyncMock()
        request.client.host = "203.0.113.5"
        assert _parse_forwarded_for(request) == "203.0.113.5"

    def test_parse_forwarded_for_returns_none_when_unavailable(self):
        request = AsyncMock(spec=Request)
        request.headers = {}
        request.client = None
        assert _parse_forwarded_for(request) is None

    def test_ip_matches_exact_address(self):
        rule = AsyncMock()
        rule.ip_or_cidr = "203.0.113.5"
        assert _ip_matches_rule("203.0.113.5", rule) is True
        assert _ip_matches_rule("203.0.113.6", rule) is False

    def test_ip_matches_cidr(self):
        rule = AsyncMock()
        rule.ip_or_cidr = "203.0.113.0/24"
        assert _ip_matches_rule("203.0.113.42", rule) is True
        assert _ip_matches_rule("203.0.114.1", rule) is False

    def test_ip_matches_invalid_cidr_returns_false(self):
        rule = AsyncMock()
        rule.ip_or_cidr = "not-a-cidr"
        assert _ip_matches_rule("203.0.113.5", rule) is False


class TestTenantIPAccessMiddleware:
    @pytest.mark.asyncio
    async def test_bypasses_when_no_tenant(self, mocker):
        from starlette.responses import Response

        from app.middleware.tenant_ip_access import TenantIPAccessMiddleware

        mock_settings = mocker.Mock()
        mock_settings.ENVIRONMENT = "development"
        mocker.patch("app.middleware.tenant_ip_access.settings", mock_settings)
        mocker.patch("app.middleware.tenant_ip_access.get_current_tenant", return_value=None)

        middleware = TenantIPAccessMiddleware(AsyncMock())
        request = AsyncMock(spec=Request)
        call_next = AsyncMock(return_value=Response("ok", status_code=200))

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_bypasses_when_no_client_ip(self, mocker):
        from starlette.responses import Response

        from app.middleware.tenant_ip_access import TenantIPAccessMiddleware

        mock_settings = mocker.Mock()
        mock_settings.ENVIRONMENT = "development"
        mocker.patch("app.middleware.tenant_ip_access.settings", mock_settings)
        mocker.patch("app.middleware.tenant_ip_access.get_current_tenant", return_value=1)
        mocker.patch("app.middleware.tenant_ip_access._parse_forwarded_for", return_value=None)

        middleware = TenantIPAccessMiddleware(AsyncMock())
        request = AsyncMock(spec=Request)
        call_next = AsyncMock(return_value=Response("ok", status_code=200))

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_bypasses_when_no_rules(self, mocker):
        from starlette.responses import Response

        from app.middleware.tenant_ip_access import TenantIPAccessMiddleware

        mock_settings = mocker.Mock()
        mock_settings.ENVIRONMENT = "development"
        mocker.patch("app.middleware.tenant_ip_access.settings", mock_settings)
        mocker.patch("app.middleware.tenant_ip_access.get_current_tenant", return_value=1)
        mocker.patch("app.middleware.tenant_ip_access._parse_forwarded_for", return_value="203.0.113.5")

        mock_session = AsyncMock()
        mock_result = mocker.Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_sm = mocker.Mock()
        mock_sm.session = mocker.Mock(return_value=mock_session)
        mocker.patch("app.core.database.sessionmanager", mock_sm)

        middleware = TenantIPAccessMiddleware(AsyncMock())
        request = AsyncMock(spec=Request)
        call_next = AsyncMock(return_value=Response("ok", status_code=200))

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_denies_matching_deny_rule(self, mocker):
        from starlette.responses import Response

        from app.middleware.tenant_ip_access import TenantIPAccessMiddleware

        mock_settings = mocker.Mock()
        mock_settings.ENVIRONMENT = "development"
        mocker.patch("app.middleware.tenant_ip_access.settings", mock_settings)
        mocker.patch("app.middleware.tenant_ip_access.get_current_tenant", return_value=1)
        mocker.patch("app.middleware.tenant_ip_access._parse_forwarded_for", return_value="203.0.113.5")

        deny_rule = mocker.Mock()
        deny_rule.ip_or_cidr = "203.0.113.5"
        deny_rule.action = "deny"

        mock_session = AsyncMock()
        mock_result = mocker.Mock()
        mock_result.scalars.return_value.all.return_value = [deny_rule]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_sm = mocker.Mock()
        mock_sm.session = mocker.Mock(return_value=mock_session)
        mocker.patch("app.core.database.sessionmanager", mock_sm)

        middleware = TenantIPAccessMiddleware(AsyncMock())
        request = AsyncMock(spec=Request)
        call_next = AsyncMock(return_value=Response("ok", status_code=200))

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_allows_matching_allow_rule(self, mocker):
        from starlette.responses import Response

        from app.middleware.tenant_ip_access import TenantIPAccessMiddleware

        mock_settings = mocker.Mock()
        mock_settings.ENVIRONMENT = "development"
        mocker.patch("app.middleware.tenant_ip_access.settings", mock_settings)
        mocker.patch("app.middleware.tenant_ip_access.get_current_tenant", return_value=1)
        mocker.patch("app.middleware.tenant_ip_access._parse_forwarded_for", return_value="203.0.113.5")

        allow_rule = mocker.Mock()
        allow_rule.ip_or_cidr = "203.0.113.5"
        allow_rule.action = "allow"

        mock_session = AsyncMock()
        mock_result = mocker.Mock()
        mock_result.scalars.return_value.all.return_value = [allow_rule]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_sm = mocker.Mock()
        mock_sm.session = mocker.Mock(return_value=mock_session)
        mocker.patch("app.core.database.sessionmanager", mock_sm)

        middleware = TenantIPAccessMiddleware(AsyncMock())
        request = AsyncMock(spec=Request)
        call_next = AsyncMock(return_value=Response("ok", status_code=200))

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_denies_when_only_allow_rules_exist_but_ip_not_matched(self, mocker):
        from starlette.responses import Response

        from app.middleware.tenant_ip_access import TenantIPAccessMiddleware

        mock_settings = mocker.Mock()
        mock_settings.ENVIRONMENT = "development"
        mocker.patch("app.middleware.tenant_ip_access.settings", mock_settings)
        mocker.patch("app.middleware.tenant_ip_access.get_current_tenant", return_value=1)
        mocker.patch("app.middleware.tenant_ip_access._parse_forwarded_for", return_value="198.51.100.1")

        allow_rule = mocker.Mock()
        allow_rule.ip_or_cidr = "203.0.113.0/24"
        allow_rule.action = "allow"

        mock_session = AsyncMock()
        mock_result = mocker.Mock()
        mock_result.scalars.return_value.all.return_value = [allow_rule]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_sm = mocker.Mock()
        mock_sm.session = mocker.Mock(return_value=mock_session)
        mocker.patch("app.core.database.sessionmanager", mock_sm)

        middleware = TenantIPAccessMiddleware(AsyncMock())
        request = AsyncMock(spec=Request)
        call_next = AsyncMock(return_value=Response("ok", status_code=200))

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 403
