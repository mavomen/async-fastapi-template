"""Tests for the minimal async Stripe REST client (request shapes + error mapping)."""

import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.billing.services import stripe_client
from app.billing.services.stripe_client import StripeError, create_checkout_session

_REAL_ASYNC_CLIENT = httpx.AsyncClient


def transport_with(handler):
    """Patch the client factory so requests flow through a MockTransport."""

    def _factory(**kwargs):
        kwargs.pop("transport", None)
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    return _factory


def use_secret(monkeypatch, key: str):
    from app.core import config

    s = config.Settings(ENVIRONMENT="test", SECRET_KEY="a" * 32, STRIPE_SECRET_KEY=key)
    monkeypatch.setattr(stripe_client, "settings", s)


class TestStripeConfigured:
    def test_false_without_key(self, monkeypatch):
        use_secret(monkeypatch, "")
        assert stripe_client.stripe_configured() is False

    def test_true_with_key(self, monkeypatch):
        use_secret(monkeypatch, "sk_test_x")
        assert stripe_client.stripe_configured() is True


@pytest.mark.asyncio
async def test_request_unconfigured_raises_503(monkeypatch):
    use_secret(monkeypatch, "")
    with pytest.raises(StripeError) as exc_info:
        await stripe_client._request("GET", "/customers")
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_subscription_returns_json(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"id": "sub_123", "status": "active"})

    use_secret(monkeypatch, "sk_test_x")
    monkeypatch.setattr(stripe_client.httpx, "AsyncClient", transport_with(handler))
    obj = await stripe_client.get_subscription("sub_123")
    assert obj["id"] == "sub_123"
    assert captured["path"] == "/v1/subscriptions/sub_123"
    assert captured["auth"].startswith("Basic ")  # key as basic-auth user


@pytest.mark.asyncio
async def test_error_response_maps_to_stripe_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            402,
            json={"error": {"message": "Card declined"}},
        )

    use_secret(monkeypatch, "sk_test_x")
    monkeypatch.setattr(stripe_client.httpx, "AsyncClient", transport_with(handler))
    with pytest.raises(StripeError, match="Card declined") as exc_info:
        await stripe_client._request("POST", "/customers", {})
    assert exc_info.value.status_code == 402


@pytest.mark.asyncio
async def test_non_json_error_body_handled(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream exploded")

    use_secret(monkeypatch, "sk_test_x")
    monkeypatch.setattr(stripe_client.httpx, "AsyncClient", transport_with(handler))
    with pytest.raises(StripeError, match="upstream"):
        await stripe_client._request("POST", "/customers", {})


class TestCheckoutSessionPayload:
    @pytest.fixture
    def plan_row(self):
        from types import SimpleNamespace

        return SimpleNamespace(
            id=3,
            name="Pro",
            price_cents=4900,
            currency="usd",
            interval="monthly",
        )

    @pytest.mark.asyncio
    async def test_form_fields_and_metadata(self, monkeypatch, plan_row):
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["form"] = parse_qs(request.content.decode())
            captured["path"] = request.url.path
            return httpx.Response(200, json={"id": "cs_1", "url": "https://pay.example/x"})

        use_secret(monkeypatch, "sk_test_x")
        monkeypatch.setattr(stripe_client.httpx, "AsyncClient", transport_with(handler))
        session_obj = await create_checkout_session(
            customer_id="cus_9",
            plan=plan_row,
            success_url="https://app.example.com/ok",
            cancel_url="https://app.example.com/no",
            tenant_id=7,
        )
        assert session_obj["url"] == "https://pay.example/x"

        form = captured["form"]
        assert captured["path"] == "/v1/checkout/sessions"
        assert form["mode"] == ["subscription"]
        assert form["customer"] == ["cus_9"]
        assert form["client_reference_id"] == ["7"]
        assert form["metadata[tenant_id]"] == ["7"]
        assert form["metadata[plan_id]"] == ["3"]
        assert form["line_items[0][price_data][unit_amount]"] == ["4900"]
        assert form["line_items[0][price_data][currency]"] == ["usd"]
        assert form["line_items[0][price_data][recurring][interval]"] == ["monthly"]
        assert form["line_items[0][price_data][product_data][name]"] == ["Pro"]

    @pytest.mark.asyncio
    async def test_yearly_interval_passthrough(self, monkeypatch, plan_row):
        plan_row.interval = "yearly"
        body: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            body.update(json.loads(json.dumps(parse_qs(request.content.decode()))))
            return httpx.Response(200, json={"id": "cs_2", "url": "https://pay.example/y"})

        use_secret(monkeypatch, "sk_test_x")
        monkeypatch.setattr(stripe_client.httpx, "AsyncClient", transport_with(handler))
        await create_checkout_session(
            customer_id="cus_9",
            plan=plan_row,
            success_url="https://a.example/ok",
            cancel_url="https://a.example/no",
            tenant_id=7,
        )
        assert body["line_items[0][price_data][recurring][interval]"] == ["yearly"]
