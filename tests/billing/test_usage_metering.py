"""Usage metering: pure units, Redis fail-open behavior, quota dependency."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.billing.api.deps import (
    _Entitlements,
    enforce_api_quota,
    invalidate_entitlements,
    resolve_entitlements,
)
from app.billing.services import usage as usage_service
from app.core.exceptions import RateLimitException
from app.main import app

NOW = datetime.now(UTC)
PERIOD_START = NOW.replace(minute=0, second=0, microsecond=0)
PERIOD_END = PERIOD_START + timedelta(days=30)


# ---------------------------------------------------------------------------
# Pure units
# ---------------------------------------------------------------------------


class TestCounterKey:
    def test_format(self):
        key = usage_service.counter_key(7, "api_requests", PERIOD_START)
        assert key == f"billing:usage:7:api_requests:{int(PERIOD_START.timestamp())}"


class TestTtlFor:
    def test_future_period_adds_grace(self):
        end = NOW + timedelta(hours=10)
        ttl = usage_service.ttl_for(end, now=NOW)
        assert ttl == 10 * 3600 + usage_service.COUNTER_TTL_GRACE_SECONDS

    def test_past_period_floors_at_60(self):
        ttl = usage_service.ttl_for(NOW - timedelta(days=1), now=NOW)
        assert ttl == 60


class TestComputeOverage:
    def test_under_included_is_zero(self):
        assert usage_service.compute_overage(100, 1_000, 5) == 0

    def test_overage_units_times_price(self):
        assert usage_service.compute_overage(1_500, 1_000, 5) == 2_500


class TestExtractMetering:
    def test_none_and_empty(self):
        assert usage_service.extract_metering(None) == {}
        assert usage_service.extract_metering({}) == {}

    def test_normalizes_config(self):
        out = usage_service.extract_metering(
            {"api_requests": {"included_quantity": 1_000, "unit_amount_cents": 3}}
        )
        assert out == {"api_requests": {"unit_amount_cents": 3, "included_quantity": 1_000}}

    def test_skips_non_dict_and_malformed(self):
        out = usage_service.extract_metering({"bad": "nope", "worse": {"unit_amount_cents": "x"}})
        assert out == {}


# ---------------------------------------------------------------------------
# Counter service (mocked Redis)
# ---------------------------------------------------------------------------


def _redis_with_pipeline(incr_result: int = 1) -> MagicMock:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.incrby = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[incr_result])
    redis.pipeline.return_value = pipe
    return redis


@pytest.mark.asyncio
async def test_increment_returns_new_value():
    with patch.object(usage_service.cache, "get_redis", return_value=_redis_with_pipeline(42)):
        value = await usage_service.increment(7, "api_requests", PERIOD_START, PERIOD_END)
    assert value == 42


@pytest.mark.asyncio
async def test_increment_fail_open_on_redis_error():
    redis = MagicMock()
    redis.pipeline.side_effect = RuntimeError("redis down")
    with patch.object(usage_service.cache, "get_redis", return_value=redis):
        assert await usage_service.increment(7, "api_requests", PERIOD_START, PERIOD_END) is None


@pytest.mark.asyncio
async def test_get_usage_reads_counter():
    redis = MagicMock()
    redis.get = AsyncMock(return_value="123")
    with patch.object(usage_service.cache, "get_redis", return_value=redis):
        assert await usage_service.get_usage(7, "api_requests", PERIOD_START) == 123


@pytest.mark.asyncio
async def test_get_usage_missing_key_is_zero():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    with patch.object(usage_service.cache, "get_redis", return_value=redis):
        assert await usage_service.get_usage(7, "api_requests", PERIOD_START) == 0


@pytest.mark.asyncio
async def test_get_usage_fail_open_on_error():
    redis = MagicMock()
    redis.get = AsyncMock(side_effect=RuntimeError("boom"))
    with patch.object(usage_service.cache, "get_redis", return_value=redis):
        assert await usage_service.get_usage(7, "api_requests", PERIOD_START) == 0


# ---------------------------------------------------------------------------
# Entitlements cache
# ---------------------------------------------------------------------------


def make_db(scalar=None):
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    db.execute = AsyncMock(return_value=result)
    return db


def make_sub(metering=None):
    plan = MagicMock(metering=metering)
    sub = MagicMock(plan=plan)
    sub.tenant_id = 7
    sub.current_period_start = PERIOD_START
    sub.current_period_end = PERIOD_END
    return sub


@pytest.fixture(autouse=True)
def _clean_cache():
    invalidate_entitlements()
    yield
    invalidate_entitlements()


@pytest.mark.asyncio
async def test_resolve_returns_none_without_subscription():
    ent = await resolve_entitlements(make_db(scalar=None), 7)
    assert ent is None


@pytest.mark.asyncio
async def test_resolve_caches_negative_lookup():
    db = make_db(scalar=None)
    assert await resolve_entitlements(db, 7) is None
    assert await resolve_entitlements(db, 7) is None
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_extracts_metering_from_plan():
    sub = make_sub({"api_requests": {"included_quantity": 500, "unit_amount_cents": 2}})
    ent = await resolve_entitlements(make_db(scalar=sub), 7)
    assert ent is not None
    assert ent.config["api_requests"] == {
        "included_quantity": 500,
        "unit_amount_cents": 2,
    }
    assert ent.period_start == PERIOD_START


@pytest.mark.asyncio
async def test_invalidate_drops_cache():
    sub = make_sub(None)
    db = make_db(scalar=sub)
    await resolve_entitlements(db, 7)
    invalidate_entitlements(7)
    await resolve_entitlements(db, 7)
    assert db.execute.await_count == 2


def test_entitlements_fresh_window():
    ent = _Entitlements({}, None, None, time_monotonic() + 60)
    assert ent.fresh() is True
    expired = _Entitlements({}, None, None, time_monotonic() - 1)
    assert expired.fresh() is False


def time_monotonic() -> float:
    import time

    return time.monotonic()


# ---------------------------------------------------------------------------
# enforce_api_quota dependency matrix
# ---------------------------------------------------------------------------


def use_quota(monkeypatch, enabled: bool = True) -> None:
    from app.core import config

    s = config.Settings(
        ENVIRONMENT="test",
        SECRET_KEY="a" * 32,
        BILLING_QUOTA_ENABLED=enabled,
    )
    monkeypatch.setattr("app.billing.api.deps.settings", s)


def make_user(tenant_id: int | None = 7):
    user = MagicMock()
    user.tenant_id = tenant_id
    return user


@pytest.mark.asyncio
async def test_disabled_flag_short_circuits(monkeypatch):
    use_quota(monkeypatch, enabled=False)
    assert await enforce_api_quota(make_db(), make_user()) is None


@pytest.mark.asyncio
async def test_anonymous_user_noops(monkeypatch):
    use_quota(monkeypatch)
    assert await enforce_api_quota(make_db(), make_user(tenant_id=None)) is None


@pytest.mark.asyncio
async def test_no_metered_dimension_passes(monkeypatch):
    use_quota(monkeypatch)
    sub = make_sub(None)
    db = make_db(scalar=sub)
    assert await enforce_api_quota(db, make_user()) is None


@pytest.mark.asyncio
async def test_within_quota_passes(monkeypatch):
    use_quota(monkeypatch)
    sub = make_sub({"api_requests": {"included_quantity": 100, "unit_amount_cents": 1}})
    db = make_db(scalar=sub)
    with patch.object(usage_service, "increment", AsyncMock(return_value=50)):
        await enforce_api_quota(db, make_user())


@pytest.mark.asyncio
async def test_over_quota_raises_429(monkeypatch):
    use_quota(monkeypatch)
    sub = make_sub({"api_requests": {"included_quantity": 100, "unit_amount_cents": 1}})
    db = make_db(scalar=sub)
    with patch.object(usage_service, "increment", AsyncMock(return_value=101)):
        with pytest.raises(RateLimitException):
            await enforce_api_quota(db, make_user())


@pytest.mark.asyncio
async def test_increment_failure_fails_open(monkeypatch):
    use_quota(monkeypatch)
    sub = make_sub({"api_requests": {"included_quantity": 100, "unit_amount_cents": 1}})
    db = make_db(scalar=sub)
    with patch.object(usage_service, "increment", AsyncMock(return_value=None)):
        await enforce_api_quota(db, make_user())


@pytest.mark.asyncio
async def test_internal_error_fails_open(monkeypatch):
    use_quota(monkeypatch)
    db = make_db()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))
    assert await enforce_api_quota(db, make_user()) is None


# ---------------------------------------------------------------------------
# Metered invoice lines (real Postgres lifecycle)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_invoice_appends_overage_lines(db_session, monkeypatch):
    from app.billing.models.plan import Plan, PlanInterval
    from app.billing.services.invoicing import generate_invoice
    from tests.billing.test_subscription_lifecycle import (
        make_subscription,
        make_tenant_row,
    )

    tenant_id = await make_tenant_row(db_session, name="metered-co")
    plan = Plan(
        name="Metered",
        slug="metered",
        description=None,
        price_cents=4900,
        currency="usd",
        interval=PlanInterval.MONTHLY,
        trial_days=0,
        is_active=True,
        metering={"api_requests": {"included_quantity": 1_000, "unit_amount_cents": 2}},
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)

    sub = make_subscription(plan.id, tenant_id)
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    async def fake_usage(tenant: int, dimension: str, period_start: datetime) -> int:
        return 1_500 if dimension == "api_requests" else 10

    monkeypatch.setattr(usage_service, "get_usage", fake_usage)
    inv = await generate_invoice(db_session, sub, plan)

    assert len(inv.lines) == 2
    overage = inv.lines[1]
    assert overage.quantity == 500
    assert overage.amount_cents == 1_000
    assert inv.subtotal_cents == 4900 + 1_000
    assert inv.total_cents == inv.subtotal_cents


@pytest.mark.asyncio
async def test_generate_invoice_skips_zero_overage(db_session, monkeypatch):
    from app.billing.models.plan import Plan, PlanInterval
    from app.billing.services.invoicing import generate_invoice
    from tests.billing.test_subscription_lifecycle import (
        make_subscription,
        make_tenant_row,
    )

    tenant_id = await make_tenant_row(db_session, name="under-quota")
    plan = Plan(
        name="UnderQuota",
        slug="under-quota",
        description=None,
        price_cents=4900,
        currency="usd",
        interval=PlanInterval.MONTHLY,
        trial_days=0,
        is_active=True,
        metering={"api_requests": {"included_quantity": 5_000, "unit_amount_cents": 2}},
    )
    db_session.add(plan)
    await db_session.commit()

    sub = make_subscription(plan.id, tenant_id)
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)

    monkeypatch.setattr(usage_service, "get_usage", AsyncMock(return_value=100))
    inv = await generate_invoice(db_session, sub, plan)
    assert len(inv.lines) == 1
    assert inv.total_cents == 4900


# ---------------------------------------------------------------------------
# GET /billing/subscriptions/usage
# ---------------------------------------------------------------------------


def _endpoint_overrides(user, session):
    from app.api.deps import get_current_user, get_current_user_or_api_key, get_db

    async def _fake_user():
        return user

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_current_user_or_api_key] = _fake_user
    app.dependency_overrides[get_db] = lambda: session


def test_usage_endpoint_reports_dimensions(mocker, client):
    from httpx import AsyncClient  # noqa: F401

    from tests.billing.test_subscription_endpoints import clear_overrides, make_user

    sub = make_sub({"api_requests": {"included_quantity": 100, "unit_amount_cents": 3}})
    plan = MagicMock(
        metering={"api_requests": {"included_quantity": 100, "unit_amount_cents": 3}}
    )

    mocker.patch(
        "app.billing.crud.subscription.subscription.get_live_for_tenant",
        new=AsyncMock(return_value=sub),
    )
    mocker.patch("app.billing.crud.plan.plan.get", new=AsyncMock(return_value=plan))
    mocker.patch.object(usage_service, "get_usage", AsyncMock(return_value=140))

    user = make_user(tenant_id=7)
    _endpoint_overrides(user, MagicMock())

    try:
        resp = client.get("/api/v1/billing/subscriptions/usage")
    finally:
        clear_overrides()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dimensions"][0]["used"] == 140
    assert body["dimensions"][0]["included_quantity"] == 100
    assert body["period_end"] is not None


def test_usage_endpoint_requires_tenant(mocker, client):
    from tests.billing.test_subscription_endpoints import clear_overrides, make_user

    user = make_user(tenant_id=None)
    _endpoint_overrides(user, MagicMock())
    try:
        resp = client.get("/api/v1/billing/subscriptions/usage")
    finally:
        clear_overrides()
    assert resp.status_code == 400
