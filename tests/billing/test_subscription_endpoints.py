"""Tests for billing REST endpoints (mocked persistence, real routing/auth)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.billing.models.subscription import SubscriptionStatus
from app.main import app

PLAN = SimpleNamespace(
    id=1,
    name="Pro",
    slug="pro",
    description=None,
    price_cents=4900,
    currency="usd",
    interval="monthly",
    trial_days=0,
    is_active=True,
)

CHEAPER_PLAN = SimpleNamespace(
    id=2,
    name="Basic",
    slug="basic",
    description=None,
    price_cents=1000,
    currency="usd",
    interval="monthly",
    trial_days=0,
    is_active=True,
)

NOW = datetime.now(UTC)


def make_sub(**overrides):
    base = SimpleNamespace(
        id=10,
        tenant_id=7,
        plan_id=1,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=NOW - timedelta(days=15),
        current_period_end=NOW + timedelta(days=15),
        trial_end=None,
        cancel_at_period_end=False,
        pending_plan_id=None,
        canceled_at=None,
        created_at=NOW,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def make_user(tenant_id=7, superuser=True):
    user = MagicMock()
    user.id = 1
    user.tenant_id = tenant_id
    user.is_active = True
    user.is_superuser = superuser
    user.roles = []
    return user


def override_deps(user, bus=None):
    """Override auth (both token paths), the event bus, and the DB session."""
    from app.api.deps import get_current_user, get_current_user_or_api_key, get_db, get_event_bus

    async def _fake_user():
        return user

    async def _fake_bus():
        return bus or AsyncMock()

    session = MagicMock()

    async def _noop(*_args):
        return None

    session.commit = _noop
    session.refresh = _noop
    session.rollback = _noop

    def _add(_obj):
        return None

    session.add = _add

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_current_user_or_api_key] = _fake_user
    app.dependency_overrides[get_event_bus] = _fake_bus
    app.dependency_overrides[get_db] = lambda: session


def clear_overrides():
    from app.api.deps import get_current_user, get_current_user_or_api_key, get_event_bus

    for dep in (get_current_user, get_current_user_or_api_key, get_event_bus):
        app.dependency_overrides.pop(dep, None)


def patch_cruds(mocker, **methods):
    """Patch methods on the crud singletons used by the endpoints."""
    patches = []
    for target, ret in methods.items():
        module, name = {
            "live": ("app.billing.crud.subscription.subscription", "get_live_for_tenant"),
            "create_sub": ("app.billing.crud.subscription.subscription", "create"),
            "get_plan": ("app.billing.crud.plan.plan", "get"),
            "by_slug": ("app.billing.crud.plan.plan", "get_by_slug"),
            "list_plans": ("app.billing.crud.plan.plan", "list_active"),
            "create_plan": ("app.billing.crud.plan.plan", "create"),
            "update_plan": ("app.billing.crud.plan.plan", "update"),
        }[target]
        patches.append(mocker.patch(f"{module}.{name}", new=AsyncMock(return_value=ret)))
    return patches


# ---------------------------------------------------------------------------
# Auth & permissions
# ---------------------------------------------------------------------------


class TestAuth:
    def test_list_plans_requires_auth(self, client):
        assert client.get("/api/v1/billing/plans").status_code == 401

    def test_create_plan_requires_auth(self, client):
        resp = client.post("/api/v1/billing/plans", json={})
        assert resp.status_code == 401

    def test_subscribe_requires_auth(self, client):
        assert client.post("/api/v1/billing/subscriptions", json={"plan_id": 1}).status_code == 401

    def test_current_requires_auth(self, client):
        assert client.get("/api/v1/billing/subscriptions/current").status_code == 401


class TestPlanPermissions:
    def test_create_plan_denied_without_billing_write(self, client):
        override_deps(make_user(superuser=False))
        try:
            resp = client.post(
                "/api/v1/billing/plans",
                json={
                    "name": "X",
                    "slug": "x",
                    "price_cents": 100,
                    "interval": "monthly",
                },
            )
            assert resp.status_code == 403
        finally:
            clear_overrides()

    def test_update_plan_denied_without_billing_write(self, client):
        override_deps(make_user(superuser=False))
        try:
            resp = client.patch("/api/v1/billing/plans/1", json={"price_cents": 200})
            assert resp.status_code == 403
        finally:
            clear_overrides()


# ---------------------------------------------------------------------------
# Plan catalog
# ---------------------------------------------------------------------------


class TestPlanEndpoints:
    def test_list_plans(self, client, mocker):
        override_deps(make_user())
        patch_cruds(mocker, list_plans=[PLAN])
        try:
            resp = client.get("/api/v1/billing/plans")
            assert resp.status_code == 200
            assert [p["slug"] for p in resp.json()["items"]] == ["pro"]
        finally:
            clear_overrides()

    def test_create_plan_conflict_on_duplicate_slug(self, client, mocker):
        override_deps(make_user())
        patch_cruds(mocker, by_slug=PLAN)
        try:
            resp = client.post(
                "/api/v1/billing/plans",
                json={
                    "name": "Dup",
                    "slug": "pro",
                    "price_cents": 100,
                    "interval": "monthly",
                },
            )
            assert resp.status_code == 409
        finally:
            clear_overrides()

    def test_deactivate_twice_is_400(self, client, mocker):
        override_deps(make_user())
        patch_cruds(mocker, get_plan=SimpleNamespace(**{**PLAN.__dict__, "is_active": False}))
        try:
            resp = client.delete("/api/v1/billing/plans/1")
            assert resp.status_code == 400
        finally:
            clear_overrides()


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


class TestSubscribe:
    def test_subscribe_without_tenant_rejected(self, client):
        override_deps(make_user(tenant_id=None, superuser=False))
        try:
            resp = client.post("/api/v1/billing/subscriptions", json={"plan_id": 1})
            assert resp.status_code == 400
            assert resp.json()["error_code"] == "BAD_REQUEST"
        finally:
            clear_overrides()

    def test_subscribe_inactive_plan_rejected(self, client, mocker):
        override_deps(make_user())
        inactive = SimpleNamespace(**{**PLAN.__dict__, "is_active": False})
        patch_cruds(mocker, get_plan=inactive)
        try:
            resp = client.post("/api/v1/billing/subscriptions", json={"plan_id": 1})
            assert resp.status_code == 400
        finally:
            clear_overrides()

    def test_subscribe_conflict_with_existing_live(self, client, mocker):
        override_deps(make_user())
        patch_cruds(mocker, get_plan=PLAN, live=make_sub())
        try:
            resp = client.post("/api/v1/billing/subscriptions", json={"plan_id": 1})
            assert resp.status_code == 409
        finally:
            clear_overrides()

    @pytest.mark.parametrize(
        ("trial_days", "expected_status"),
        [(0, "active"), (14, "trialing")],
    )
    def test_subscribe_success_paths(self, client, mocker, trial_days, expected_status):
        override_deps(make_user(), bus=AsyncMock(publish=AsyncMock()))
        plan_row = SimpleNamespace(**{**PLAN.__dict__, "trial_days": trial_days})

        created = make_sub(
            status=SubscriptionStatus.TRIALING if trial_days else SubscriptionStatus.ACTIVE,
            trial_end=NOW + timedelta(days=trial_days) if trial_days else None,
        )
        patch_cruds(mocker, get_plan=plan_row, live=None, create_sub=created)
        try:
            resp = client.post("/api/v1/billing/subscriptions", json={"plan_id": 1})
            assert resp.status_code == 201
            assert resp.json()["subscription"]["status"] == expected_status
        finally:
            clear_overrides()


class TestChangeAndCancel:
    def test_change_to_same_plan_rejected(self, client, mocker):
        override_deps(make_user())
        patch_cruds(mocker, live=make_sub(plan_id=1), get_plan=PLAN)
        try:
            resp = client.post("/api/v1/billing/subscriptions/change-plan", json={"plan_id": 1})
            assert resp.status_code == 400
        finally:
            clear_overrides()

    def test_upgrade_immediate_returns_preview_and_resets_period(self, client, mocker):
        override_deps(make_user(), bus=AsyncMock(publish=AsyncMock()))
        sub = make_sub()
        premium = SimpleNamespace(**{**PLAN.__dict__, "id": 3, "slug": "max", "price_cents": 9900})

        def fake_get(db, plan_id):
            return {1: PLAN, 3: premium}[plan_id]

        mocker.patch(
            "app.billing.crud.subscription.subscription.get_live_for_tenant",
            new=AsyncMock(return_value=sub),
        )
        mocker.patch("app.billing.crud.plan.plan.get", new=AsyncMock(side_effect=fake_get))

        try:
            resp = client.post("/api/v1/billing/subscriptions/change-plan", json={"plan_id": 3})
            assert resp.status_code == 200
            body = resp.json()
            assert body["subscription"]["plan_id"] == 3
            assert body["preview"] is not None
            # halfway through the period at 9900 vs 4900: net charge is positive
            assert body["preview"]["net_cents"] > 0
            assert body["applied_plan_id"] is None
        finally:
            clear_overrides()

    def test_downgrade_schedules_pending_plan(self, client, mocker):
        override_deps(make_user(), bus=AsyncMock(publish=AsyncMock()))
        sub = make_sub()

        def fake_get(db, plan_id):
            return {1: PLAN, 2: CHEAPER_PLAN}[plan_id]

        mocker.patch(
            "app.billing.crud.subscription.subscription.get_live_for_tenant",
            new=AsyncMock(return_value=sub),
        )
        mocker.patch("app.billing.crud.plan.plan.get", new=AsyncMock(side_effect=fake_get))

        try:
            resp = client.post(
                "/api/v1/billing/subscriptions/change-plan", json={"plan_id": CHEAPER_PLAN.id}
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["preview"] is None
            assert body["applied_plan_id"] == CHEAPER_PLAN.id
            assert sub.pending_plan_id == CHEAPER_PLAN.id
        finally:
            clear_overrides()

    def test_cancel_scheduled_sets_flag(self, client, mocker):
        override_deps(make_user(), bus=AsyncMock(publish=AsyncMock()))
        sub = make_sub()
        patch_cruds(mocker, live=sub)

        try:
            resp = client.post("/api/v1/billing/subscriptions/cancel", json={"immediate": False})
            assert resp.status_code == 200
            assert sub.cancel_at_period_end is True
        finally:
            clear_overrides()

    def test_trial_cannot_schedule_cancel(self, client, mocker):
        override_deps(make_user())
        sub = make_sub(status=SubscriptionStatus.TRIALING, trial_end=NOW + timedelta(days=7))
        patch_cruds(mocker, live=sub)
        try:
            resp = client.post("/api/v1/billing/subscriptions/cancel", json={"immediate": False})
            assert resp.status_code == 400
        finally:
            clear_overrides()

    def test_resume_requires_scheduled_cancel(self, client, mocker):
        override_deps(make_user())
        patch_cruds(mocker, live=make_sub(cancel_at_period_end=False))
        try:
            resp = client.post("/api/v1/billing/subscriptions/resume")
            assert resp.status_code == 400
        finally:
            clear_overrides()

    def test_no_live_subscription_is_404(self, client, mocker):
        override_deps(make_user())
        patch_cruds(mocker, live=None)
        try:
            resp = client.get("/api/v1/billing/subscriptions/current")
            assert resp.status_code == 404
        finally:
            clear_overrides()
