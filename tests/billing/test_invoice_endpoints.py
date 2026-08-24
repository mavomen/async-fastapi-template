"""Tests for /billing/invoices endpoints (mocked persistence, real routing/auth)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.billing.models.invoice import InvoiceStatus
from tests.billing.test_subscription_endpoints import (
    PLAN,
    clear_overrides,
    make_sub,
    make_user,
    override_deps,
    patch_cruds,
)

LIST_URL = "/api/v1/billing/invoices"


def make_invoice(**overrides):
    line = SimpleNamespace(
        id=100,
        invoice_id=500,
        description="Pro — subscription period",
        quantity=1,
        unit_amount_cents=4900,
        tax_rate_bps=0,
        amount_cents=4900,
    )
    base = SimpleNamespace(
        id=500,
        tenant_id=7,
        subscription_id=10,
        status=InvoiceStatus.DRAFT,
        currency="usd",
        subtotal_cents=4900,
        tax_cents=0,
        total_cents=4900,
        period_start=datetime(2026, 8, 1, tzinfo=UTC),
        period_end=datetime(2026, 8, 31, tzinfo=UTC),
        issued_at=None,
        paid_at=None,
        created_at=datetime(2026, 8, 24, tzinfo=UTC),
        lines=[line],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class TestAuth:
    def test_list_requires_auth(self, client):
        assert client.get(LIST_URL).status_code == 401

    def test_detail_requires_auth(self, client):
        assert client.get(f"{LIST_URL}/500").status_code == 401

    def test_generate_requires_auth(self, client):
        resp = client.post(f"{LIST_URL}/generate", json={})
        assert resp.status_code == 401

    def test_issue_requires_auth(self, client):
        assert client.post(f"{LIST_URL}/500/issue").status_code == 401


class TestListAndDetail:
    def test_list_returns_tenant_invoices(self, client, mocker):
        override_deps(make_user())
        mocker.patch(
            "app.billing.crud.invoice.invoice.list_for_tenant",
            new=AsyncMock(return_value=[make_invoice()]),
        )
        try:
            resp = client.get(LIST_URL)
            assert resp.status_code == 200
            items = resp.json()["items"]
            assert len(items) == 1
            assert items[0]["total_cents"] == 4900
            assert items[0]["lines"][0]["description"].startswith("Pro")
        finally:
            clear_overrides()

    def test_detail_not_found_for_other_tenant(self, client, mocker):
        override_deps(make_user())
        mocker.patch(
            "app.billing.crud.invoice.invoice.get_for_tenant",
            new=AsyncMock(return_value=None),
        )
        try:
            resp = client.get(f"{LIST_URL}/999")
            assert resp.status_code == 404
        finally:
            clear_overrides()

    def test_detail_without_tenant_is_404(self, client, mocker):
        override_deps(make_user(tenant_id=None))
        mocker.patch(
            "app.billing.crud.invoice.invoice.get_for_tenant",
            new=AsyncMock(return_value=None),
        )
        try:
            assert client.get(f"{LIST_URL}/500").status_code == 404
        finally:
            clear_overrides()


class TestGenerate:
    def test_without_live_subscription_404(self, client, mocker):
        override_deps(make_user())
        patch_cruds(mocker, live=None)
        try:
            resp = client.post(f"{LIST_URL}/generate", json={})
            assert resp.status_code == 404
        finally:
            clear_overrides()

    def test_user_without_tenant_rejected(self, client):
        # superuser passes the billing:write route guard; handler then rejects
        override_deps(make_user(tenant_id=None, superuser=True))
        try:
            resp = client.post(f"{LIST_URL}/generate", json={})
            assert resp.status_code == 400
        finally:
            clear_overrides()

    def test_success_publishes_generated_event(self, client, mocker):
        override_deps(make_user(), bus=AsyncMock(publish=AsyncMock()))
        patch_cruds(mocker, live=make_sub(), get_plan=PLAN)

        inv = make_invoice(status=InvoiceStatus.DRAFT)
        gen_mock = AsyncMock(return_value=inv)
        mocker.patch(
            "app.billing.api.endpoints.invoices.invoicing_service.generate_invoice", new=gen_mock
        )

        try:
            resp = client.post(f"{LIST_URL}/generate", json={})
            assert resp.status_code == 201
            assert resp.json()["status"] == "draft"
            gen_mock.assert_awaited_once()
        finally:
            clear_overrides()


class TestLifecycleActions:
    @pytest.mark.parametrize(
        ("action", "service_fn"),
        [("issue", "issue"), ("pay", "mark_paid"), ("void", "void")],
    )
    def test_actions_route_through_service_and_publish(self, client, mocker, action, service_fn):
        override_deps(make_user(), bus=AsyncMock(publish=AsyncMock()))
        final_status = {
            "issue": InvoiceStatus.OPEN,
            "pay": InvoiceStatus.PAID,
            "void": InvoiceStatus.VOID,
        }[action]
        mocker.patch(
            "app.billing.crud.invoice.invoice.get_for_tenant",
            new=AsyncMock(return_value=make_invoice()),
        )
        svc_mock = AsyncMock(return_value=make_invoice(status=final_status))
        mocker.patch(
            f"app.billing.api.endpoints.invoices.invoicing_service.{service_fn}", new=svc_mock
        )
        try:
            resp = client.post(f"{LIST_URL}/500/{action}")
            assert resp.status_code == 200
            assert resp.json()["status"] == str(final_status)
            svc_mock.assert_awaited_once()
        finally:
            clear_overrides()

    def test_action_on_foreign_invoice_is_404(self, client, mocker):
        override_deps(make_user())
        mocker.patch(
            "app.billing.crud.invoice.invoice.get_for_tenant",
            new=AsyncMock(return_value=None),
        )
        try:
            assert client.post(f"{LIST_URL}/999/void").status_code == 404
        finally:
            clear_overrides()
