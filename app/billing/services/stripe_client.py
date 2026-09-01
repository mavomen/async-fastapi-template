"""Minimal async Stripe REST client (httpx).

Only the handful of operations this integration needs — no SDK
dependency. All calls are async-native; errors surface as StripeError.
"""

from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import settings

if TYPE_CHECKING:
    from app.billing.models.plan import Plan


class StripeError(Exception):
    """Raised when the Stripe API returns a non-success response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"Stripe error {status_code}: {message}")


def stripe_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def _auth() -> tuple[str, str]:
    return (settings.STRIPE_SECRET_KEY, "")


async def _request(
    method: str,
    path: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not stripe_configured():
        raise StripeError(503, "Stripe is not configured")
    async with httpx.AsyncClient(
        base_url=settings.STRIPE_API_BASE_URL,
        auth=_auth(),
        timeout=15.0,
    ) as client:
        resp = await client.request(method, path, data=data)
    if resp.status_code >= 400:
        detail = ""
        try:
            body = resp.json()
            detail = str(body.get("error", {}).get("message", ""))
        except ValueError:
            detail = resp.text[:200]
        raise StripeError(resp.status_code, detail)
    result: dict[str, Any] = resp.json()
    return result


async def create_customer(name: str, email: str | None = None) -> dict[str, Any]:
    """Create a Stripe customer; returns the customer object."""
    payload: dict[str, Any] = {"name": name}
    if email:
        payload["email"] = email
    return await _request("POST", "/customers", payload)


async def create_checkout_session(
    *,
    customer_id: str,
    plan: Plan,
    success_url: str,
    cancel_url: str,
    tenant_id: int,
) -> dict[str, Any]:
    """Create a hosted checkout session for a subscription.

    Uses inline ``price_data`` built from our catalog Plan so no Stripe
    Price objects need syncing. Tenant/plan ride along in metadata.
    """
    interval = getattr(plan.interval, "value", plan.interval)
    payload: dict[str, Any] = {
        "mode": "subscription",
        "customer": customer_id,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(tenant_id),
        "metadata[tenant_id]": str(tenant_id),
        "metadata[plan_id]": str(plan.id),
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": plan.currency,
        "line_items[0][price_data][unit_amount]": str(plan.price_cents),
        "line_items[0][price_data][recurring][interval]": str(interval),
        "line_items[0][price_data][product_data][name]": plan.name,
    }
    return await _request("POST", "/checkout/sessions", payload)


async def get_subscription(subscription_id: str) -> dict[str, Any]:
    """Retrieve a Stripe subscription object."""
    return await _request("GET", f"/subscriptions/{subscription_id}")


async def create_refund(
    payment_intent: str | None = None,
    charge: str | None = None,
    *,
    amount_cents: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Issue a refund against a Stripe charge or payment intent.

    ``amount_cents`` defaults to a full refund when omitted. ``reason``
    is informational only (duplicate, fraudulent, requested_by_customer).
    """
    if payment_intent is None and charge is None:
        raise ValueError("create_refund requires payment_intent or charge")

    payload: dict[str, Any] = {}
    if payment_intent is not None:
        payload["payment_intent"] = payment_intent
    if charge is not None:
        payload["charge"] = charge
    if amount_cents is not None:
        payload["amount"] = str(amount_cents)
    if reason:
        payload["reason"] = reason
    return await _request("POST", "/refunds", payload)
