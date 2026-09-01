"""Tests for /billing/stripe endpoints (webhook intake + checkout session)."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.signing import build_signature_header
from app.main import app
from tests.billing.test_subscription_endpoints import (
    PLAN,
    clear_overrides,
    make_user,
    override_deps,
)

WEBHOOK_URL = "/api/v1/billing/stripe/webhook"
CHECKOUT_URL = "/api/v1/billing/stripe/checkout-session"


def patch_settings(monkeypatch, **overrides):
    """Settings is frozen; swap in a fresh instance for the stripe modules."""
    from app.core import config

    s = config.Settings(ENVIRONMENT="test", SECRET_KEY="a" * 32, **overrides)
    monkeypatch.setattr("app.billing.services.stripe_client.settings", s)
    monkeypatch.setattr("app.billing.api.endpoints.stripe.settings", s)
    return s


@pytest.fixture
def stripe_enabled(monkeypatch):
    patch_settings(monkeypatch, STRIPE_SECRET_KEY="sk_test_abc", STRIPE_WEBHOOK_SECRET="whsec_test")


def signed_post(client, body: bytes, secret: str = "whsec_test", ts: int | None = None):
    sig = build_signature_header(body, secret, ts if ts is not None else int(time.time()))
    return client.post(
        WEBHOOK_URL,
        content=body,
        headers={"content-type": "application/json", "stripe-signature": sig},
    )


def patch_stripe_events(mocker, *, outcome="created"):
    """process_event owns the full pipeline (ledger included); mock it wholesale."""
    import app.billing.services.stripe_events as svc

    if isinstance(outcome, BaseException):
        mock = AsyncMock(side_effect=outcome)
    else:
        mock = AsyncMock(return_value=outcome)
    mocker.patch.object(svc, "process_event", new=mock)


# ---------------------------------------------------------------------------
# Webhook intake
# ---------------------------------------------------------------------------


class TestWebhookGuards:
    def test_unconfigured_returns_503(self, client):
        resp = client.post(WEBHOOK_URL, json={"id": "evt_1", "type": "x"})
        assert resp.status_code == 503

    def test_missing_signature_rejected(self, client, stripe_enabled):
        resp = client.post(
            WEBHOOK_URL,
            content=b"{}",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_bad_signature_rejected(self, client, stripe_enabled):
        resp = signed_post(client, b"{}", secret="wrong-secret")
        assert resp.status_code == 400

    def test_stale_timestamp_rejected(self, client, stripe_enabled):
        stale_ts = int(time.time()) - 10_000
        resp = signed_post(client, b"{}", ts=stale_ts)
        assert resp.status_code == 400

    def test_invalid_json_rejected(self, client, stripe_enabled):
        resp = signed_post(client, b"not-json")
        assert resp.status_code == 400

    @pytest.mark.parametrize(
        "payload",
        [{"type": "no-id"}, {"id": ""}, {}],
        ids=["missing-id", "empty-id", "empty-body"],
    )
    def test_missing_id_or_type_rejected(self, client, stripe_enabled, payload):
        import json

        resp = signed_post(client, json.dumps(payload).encode())
        assert resp.status_code == 400


class TestWebhookProcessing:
    def test_duplicate_delivery_short_circuits(self, client, mocker, stripe_enabled):
        patch_stripe_events(mocker, outcome="duplicate")
        resp = signed_post(client, b'{"id":"evt_dup","type":"invoice.payment_failed"}')
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "duplicate"

    def test_verified_event_processed_and_acked(self, client, mocker, stripe_enabled):
        patch_stripe_events(mocker)
        resp = signed_post(client, b'{"id":"evt_ok","type":"checkout.session.completed"}')
        assert resp.status_code == 200
        assert resp.json() == {"received": True, "outcome": "created"}

    def test_illegal_transition_acknowledged_as_rejected(self, client, mocker, stripe_enabled):
        import app.billing.services.stripe_events as svc
        from app.billing.services.billing import IllegalTransitionError

        mocker.patch.object(
            svc,
            "process_event",
            new=AsyncMock(side_effect=IllegalTransitionError("canceled", "active")),
        )
        resp = signed_post(client, b'{"id":"evt_bad","type":"customer.subscription.updated"}')
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "rejected"

    def test_processing_error_logged_not_500(self, client, mocker, stripe_enabled):
        patch_stripe_events(mocker, outcome=RuntimeError("boom"))
        resp = signed_post(client, b'{"id":"evt_err","type":"checkout.session.completed"}')
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "error"

    def test_unknown_event_type_is_ignored(self, client, mocker, stripe_enabled):
        patch_stripe_events(mocker, outcome="ignored")
        resp = signed_post(client, b'{"id":"evt_x","type":"charge.refunded"}')
        assert resp.json()["outcome"] == "ignored"


# ---------------------------------------------------------------------------
# Checkout session endpoint
# ---------------------------------------------------------------------------


def make_tenant_session(db, tenant=None):
    """Give the overridden MagicMock session an execute() returning the tenant."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=tenant)
    db.execute = AsyncMock(return_value=result)


class TestCheckoutSession:
    def test_requires_auth(self, client):
        assert client.post(CHECKOUT_URL, json={"plan_id": 1}).status_code == 401

    def test_unconfigured_returns_503(self, client):
        override_deps(make_user())
        try:
            resp = client.post(
                CHECKOUT_URL,
                json={
                    "plan_id": 1,
                    "success_url": "https://app.example.com/ok",
                    "cancel_url": "https://app.example.com/no",
                },
            )
            assert resp.status_code == 503
        finally:
            clear_overrides()

    def test_user_without_tenant_rejected(self, client, stripe_enabled):
        override_deps(make_user(tenant_id=None))
        try:
            resp = client.post(
                CHECKOUT_URL,
                json={
                    "plan_id": 1,
                    "success_url": "https://app.example.com/ok",
                    "cancel_url": "https://app.example.com/no",
                },
            )
            assert resp.status_code == 400
        finally:
            clear_overrides()

    def test_unknown_plan_returns_404(self, client, mocker, stripe_enabled):
        from tests.billing.test_subscription_endpoints import patch_cruds

        override_deps(make_user())
        patch_cruds(mocker, get_plan=None, live=None)
        try:
            resp = client.post(
                CHECKOUT_URL,
                json={
                    "plan_id": 999,
                    "success_url": "https://app.example.com/ok",
                    "cancel_url": "https://app.example.com/no",
                },
            )
            assert resp.status_code == 404
        finally:
            clear_overrides()

    def test_existing_live_subscription_conflicts(self, client, mocker, stripe_enabled):
        from datetime import UTC, datetime, timedelta

        from tests.billing.test_subscription_endpoints import make_sub, patch_cruds

        override_deps(make_user())
        sub = make_sub(current_period_end=datetime.now(UTC) + timedelta(days=5))
        patch_cruds(mocker, get_plan=PLAN, live=sub)
        try:
            resp = client.post(
                CHECKOUT_URL,
                json={
                    "plan_id": 1,
                    "success_url": "https://app.example.com/ok",
                    "cancel_url": "https://app.example.com/no",
                },
            )
            assert resp.status_code == 409
        finally:
            clear_overrides()

    def test_provisions_customer_and_returns_url(self, client, mocker, stripe_enabled):
        from tests.billing.test_subscription_endpoints import patch_cruds

        user = make_user()
        tenant_row = SimpleNamespace(id=7, name="Acme", stripe_customer_id=None)
        override_deps(user)

        # the overridden session's add/commit are noops; wire execute() -> tenant
        session = app.dependency_overrides[__import__("app.api.deps", fromlist=["get_db"]).get_db]()
        make_tenant_session(session, tenant_row)

        patch_cruds(mocker, get_plan=PLAN, live=None)
        mocker.patch(
            "app.billing.api.endpoints.stripe.create_customer",
            new=AsyncMock(return_value={"id": "cus_new123"}),
        )
        mocker.patch(
            "app.billing.api.endpoints.stripe.create_checkout_session",
            new=AsyncMock(return_value={"id": "cs_1", "url": "https://checkout.stripe.com/x"}),
        )
        try:
            resp = client.post(
                CHECKOUT_URL,
                json={
                    "plan_id": 1,
                    "success_url": "https://app.example.com/ok",
                    "cancel_url": "https://app.example.com/no",
                },
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["url"].startswith("https://")
            assert body["session_id"] == "cs_1"
            assert tenant_row.stripe_customer_id == "cus_new123"
        finally:
            clear_overrides()

    def test_existing_customer_reused_without_provisioning(self, client, mocker, stripe_enabled):
        from tests.billing.test_subscription_endpoints import patch_cruds

        tenant_row = SimpleNamespace(id=7, name="Acme", stripe_customer_id="cus_exists")
        override_deps(make_user())
        session = app.dependency_overrides[__import__("app.api.deps", fromlist=["get_db"]).get_db]()
        make_tenant_session(session, tenant_row)

        patch_cruds(mocker, get_plan=PLAN, live=None)
        provision_mock = AsyncMock(return_value={"id": "cus_should_not_be_called"})
        mocker.patch("app.billing.api.endpoints.stripe.create_customer", new=provision_mock)
        mocker.patch(
            "app.billing.api.endpoints.stripe.create_checkout_session",
            new=AsyncMock(return_value={"id": "cs_2", "url": "https://checkout.stripe.com/y"}),
        )
        try:
            resp = client.post(
                CHECKOUT_URL,
                json={
                    "plan_id": 1,
                    "success_url": "https://app.example.com/ok",
                    "cancel_url": "https://app.example.com/no",
                },
            )
            assert resp.status_code == 200
            provision_mock.assert_not_called()
        finally:
            clear_overrides()
