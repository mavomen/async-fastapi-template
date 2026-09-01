"""Tests for billing admin action routes (override-plan, set-status, refund)."""

from datetime import UTC, datetime

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models.invoice import Invoice, InvoiceStatus
from app.billing.models.plan import Plan
from app.billing.models.subscription import Subscription, SubscriptionStatus
from app.identity.crud.user import user as crud_user
from app.identity.models.tenant import Tenant
from app.identity.schemas.user import UserCreate

_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _transport_with(handler):
    """Patch the client factory so requests flow through a MockTransport."""

    def _factory(**kwargs):
        kwargs.pop("transport", None)
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    return _factory


@pytest.fixture
async def tenant_fixture(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(name="acme")
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def csrf_headers(async_client: AsyncClient, db_session: AsyncSession) -> dict:
    """Superuser auth + CSRF pair with auth deps overridden (no Redis needed)."""
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="superadmin@test.com", username="superadmin", password="AdminPass1!"
        ),
    )
    user.is_superuser = True
    await db_session.commit()

    from unittest.mock import AsyncMock

    from app.api.deps import get_current_user, get_current_user_or_api_key, get_event_bus
    from app.main import app

    async def _fake_user():
        return user

    async def _fake_bus():
        return AsyncMock()

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_current_user_or_api_key] = _fake_user
    app.dependency_overrides[get_event_bus] = _fake_bus

    try:
        from app.middleware.csrf import _make_token
        from app.middleware.csrf import settings as csrf_settings

        csrf = _make_token(csrf_settings.SECRET_KEY)
        async_client.cookies.set("csrf_token", csrf)
        yield {"X-CSRF-Token": csrf}
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_user_or_api_key, None)
        app.dependency_overrides.pop(get_event_bus, None)


@pytest.fixture
async def plan_fixture(db_session: AsyncSession) -> Plan:
    p = Plan(
        name="Pro",
        slug="pro",
        price_cents=2500,
        currency="usd",
        interval="monthly",
        is_active=True,
    )
    db_session.add(p)
    await db_session.commit()
    return p


@pytest.fixture
async def inactive_plan_fixture(db_session: AsyncSession) -> Plan:
    p = Plan(
        name="Legacy",
        slug="legacy",
        price_cents=999,
        currency="usd",
        interval="monthly",
        is_active=False,
    )
    db_session.add(p)
    await db_session.commit()
    return p


@pytest.fixture
async def sub_fixture(
    db_session: AsyncSession, plan_fixture: Plan, tenant_fixture: Tenant
) -> Subscription:
    sub = Subscription(
        plan_id=plan_fixture.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime(2025, 1, 1, tzinfo=UTC),
        current_period_end=datetime(2025, 2, 1, tzinfo=UTC),
        tenant_id=tenant_fixture.id,
    )
    db_session.add(sub)
    await db_session.commit()
    return sub


@pytest.fixture
async def paid_invoice_fixture(db_session: AsyncSession, sub_fixture: Subscription) -> Invoice:
    inv = Invoice(
        subscription_id=sub_fixture.id,
        status=InvoiceStatus.PAID,
        currency="usd",
        subtotal_cents=2500,
        tax_cents=0,
        total_cents=2500,
        period_start=sub_fixture.current_period_start,
        period_end=sub_fixture.current_period_end,
        tenant_id=sub_fixture.tenant_id,
    )
    db_session.add(inv)
    await db_session.commit()
    return inv


@pytest.fixture
async def draft_invoice_fixture(db_session: AsyncSession, sub_fixture: Subscription) -> Invoice:
    inv = Invoice(
        subscription_id=sub_fixture.id,
        status=InvoiceStatus.DRAFT,
        currency="usd",
        subtotal_cents=2500,
        tax_cents=0,
        total_cents=2500,
        period_start=sub_fixture.current_period_start,
        period_end=sub_fixture.current_period_end,
        tenant_id=sub_fixture.tenant_id,
    )
    db_session.add(inv)
    await db_session.commit()
    return inv


# --- override-plan ----------------------------------------------------------


@pytest.mark.asyncio
async def test_override_plan_invalid_plan_returns_404(
    async_client: AsyncClient,
    csrf_headers: dict,
    sub_fixture: Subscription,
):
    resp = await async_client.post(
        f"/admin/subscriptions/{sub_fixture.id}/override-plan",
        data={"plan_id": "999999"},
        headers=csrf_headers,
    )
    assert resp.status_code == 404, resp.text
    assert "Plan not found" in resp.text


@pytest.mark.asyncio
async def test_override_plan_inactive_plan_returns_404(
    async_client: AsyncClient,
    csrf_headers: dict,
    sub_fixture: Subscription,
    inactive_plan_fixture: Plan,
):
    resp = await async_client.post(
        f"/admin/subscriptions/{sub_fixture.id}/override-plan",
        data={"plan_id": str(inactive_plan_fixture.id)},
        headers=csrf_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_override_plan_success(
    async_client: AsyncClient,
    csrf_headers: dict,
    sub_fixture: Subscription,
    plan_fixture: Plan,
    db_session: AsyncSession,
):
    resp = await async_client.post(
        f"/admin/subscriptions/{sub_fixture.id}/override-plan",
        data={"plan_id": str(plan_fixture.id)},
        headers=csrf_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/admin/subscriptions/{sub_fixture.id}"

    await db_session.refresh(sub_fixture)
    assert sub_fixture.plan_id == plan_fixture.id
    assert sub_fixture.pending_plan_id is None


# --- set-status -------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_status_invalid_transition_returns_400(
    async_client: AsyncClient,
    csrf_headers: dict,
    sub_fixture: Subscription,
):
    # ACTIVE -> ACTIVE is not a valid transition (must go through past_due/canceled)
    resp = await async_client.post(
        f"/admin/subscriptions/{sub_fixture.id}/set-status",
        data={"status": "active"},
        headers=csrf_headers,
    )
    assert resp.status_code == 400
    assert "Allowed" in resp.text


@pytest.mark.asyncio
async def test_set_status_invalid_enum_returns_400(
    async_client: AsyncClient,
    csrf_headers: dict,
    sub_fixture: Subscription,
):
    resp = await async_client.post(
        f"/admin/subscriptions/{sub_fixture.id}/set-status",
        data={"status": "banana"},
        headers=csrf_headers,
    )
    assert resp.status_code == 400
    assert "Unknown status" in resp.text


@pytest.mark.asyncio
async def test_set_status_success(
    async_client: AsyncClient,
    csrf_headers: dict,
    sub_fixture: Subscription,
    db_session: AsyncSession,
):
    resp = await async_client.post(
        f"/admin/subscriptions/{sub_fixture.id}/set-status",
        data={"status": "past_due"},
        headers=csrf_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303

    await db_session.refresh(sub_fixture)
    assert sub_fixture.status == SubscriptionStatus.PAST_DUE


@pytest.mark.asyncio
async def test_set_status_past_due_to_active_resets_dunning(
    async_client: AsyncClient,
    csrf_headers: dict,
    sub_fixture: Subscription,
    db_session: AsyncSession,
):
    # move to past_due first
    sub_fixture.status = SubscriptionStatus.PAST_DUE
    sub_fixture.failed_payment_count = 2
    db_session.add(sub_fixture)
    await db_session.commit()

    resp = await async_client.post(
        f"/admin/subscriptions/{sub_fixture.id}/set-status",
        data={"status": "active"},
        headers=csrf_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    await db_session.refresh(sub_fixture)
    assert sub_fixture.failed_payment_count == 0


@pytest.mark.asyncio
async def test_set_status_to_suspended_sets_suspended_at(
    async_client: AsyncClient,
    csrf_headers: dict,
    sub_fixture: Subscription,
    db_session: AsyncSession,
):
    sub_fixture.status = SubscriptionStatus.PAST_DUE
    db_session.add(sub_fixture)
    await db_session.commit()

    resp = await async_client.post(
        f"/admin/subscriptions/{sub_fixture.id}/set-status",
        data={"status": "suspended"},
        headers=csrf_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    await db_session.refresh(sub_fixture)
    assert sub_fixture.status == SubscriptionStatus.SUSPENDED
    assert sub_fixture.suspended_at is not None


@pytest.mark.asyncio
async def test_set_status_to_canceled_sets_canceled_at(
    async_client: AsyncClient,
    csrf_headers: dict,
    sub_fixture: Subscription,
    db_session: AsyncSession,
):
    resp = await async_client.post(
        f"/admin/subscriptions/{sub_fixture.id}/set-status",
        data={"status": "canceled"},
        headers=csrf_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    await db_session.refresh(sub_fixture)
    assert sub_fixture.status == SubscriptionStatus.CANCELED
    assert sub_fixture.canceled_at is not None


# --- refund ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refund_non_paid_returns_400(
    async_client: AsyncClient,
    csrf_headers: dict,
    draft_invoice_fixture: Invoice,
):
    resp = await async_client.post(
        f"/admin/invoices/{draft_invoice_fixture.id}/refund",
        data={"payment_reference": "charge_abc123"},
        headers=csrf_headers,
    )
    assert resp.status_code == 400
    assert "Only paid" in resp.text


@pytest.mark.asyncio
async def test_refund_missing_payment_reference_returns_400(
    async_client: AsyncClient,
    csrf_headers: dict,
    paid_invoice_fixture: Invoice,
):
    resp = await async_client.post(
        f"/admin/invoices/{paid_invoice_fixture.id}/refund",
        data={},
        headers=csrf_headers,
    )
    assert resp.status_code == 400
    assert "payment_reference required" in resp.text


@pytest.mark.asyncio
async def test_refund_bad_prefix_returns_400(
    async_client: AsyncClient,
    csrf_headers: dict,
    paid_invoice_fixture: Invoice,
):
    resp = await async_client.post(
        f"/admin/invoices/{paid_invoice_fixture.id}/refund",
        data={"payment_reference": "tok_invalid"},
        headers=csrf_headers,
    )
    assert resp.status_code == 400
    assert "pi_ or charge_" in resp.text


@pytest.mark.asyncio
async def test_refund_negative_amount_returns_400(
    async_client: AsyncClient,
    csrf_headers: dict,
    paid_invoice_fixture: Invoice,
):
    resp = await async_client.post(
        f"/admin/invoices/{paid_invoice_fixture.id}/refund",
        data={"payment_reference": "charge_abc123", "amount_cents": "-100"},
        headers=csrf_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refund_stripe_503_when_unconfigured(
    async_client: AsyncClient,
    csrf_headers: dict,
    paid_invoice_fixture: Invoice,
    monkeypatch,
):
    from app.billing.services import stripe_client

    s = stripe_client.settings.model_copy(update={"STRIPE_SECRET_KEY": ""})
    monkeypatch.setattr(stripe_client, "settings", s)

    resp = await async_client.post(
        f"/admin/invoices/{paid_invoice_fixture.id}/refund",
        data={"payment_reference": "charge_abc123"},
        headers=csrf_headers,
    )
    assert resp.status_code == 503
    assert "not configured" in resp.text


@pytest.mark.asyncio
async def test_refund_success_charge(
    async_client: AsyncClient,
    csrf_headers: dict,
    paid_invoice_fixture: Invoice,
    monkeypatch,
):
    from app.billing.services import stripe_client

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "re_123", "status": "succeeded"})

    monkeypatch.setattr(httpx, "AsyncClient", _transport_with(_handler))
    s = stripe_client.settings.model_copy(update={"STRIPE_SECRET_KEY": "sk_test_x"})
    monkeypatch.setattr(stripe_client, "settings", s)

    resp = await async_client.post(
        f"/admin/invoices/{paid_invoice_fixture.id}/refund",
        data={"payment_reference": "charge_abc123"},
        headers=csrf_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/admin/invoices/{paid_invoice_fixture.id}"


@pytest.mark.asyncio
async def test_refund_success_with_amount(
    async_client: AsyncClient,
    csrf_headers: dict,
    paid_invoice_fixture: Invoice,
    monkeypatch,
):
    from app.billing.services import stripe_client

    captured = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={"id": "re_456", "status": "succeeded"})

    monkeypatch.setattr(httpx, "AsyncClient", _transport_with(_handler))
    s = stripe_client.settings.model_copy(update={"STRIPE_SECRET_KEY": "sk_test_x"})
    monkeypatch.setattr(stripe_client, "settings", s)

    resp = await async_client.post(
        f"/admin/invoices/{paid_invoice_fixture.id}/refund",
        data={"payment_reference": "pi_xyz789", "amount_cents": "1500"},
        headers=csrf_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert b"amount" in captured["body"]
