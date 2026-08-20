"""Tests for custom Prometheus metrics registration and wiring."""

from prometheus_client import REGISTRY

from app.core.metrics import (
    db_active_queries,
    db_pool_active,
    db_query_duration_seconds,
)


def test_new_db_metrics_registered() -> None:
    """New db_active_queries and db_query_duration_seconds are registered."""
    registered = {mf.name for mf in REGISTRY.collect()}
    assert "db_active_queries" in registered
    assert "db_query_duration_seconds" in registered


def test_existing_db_metrics_registered() -> None:
    """Original db pool metrics remain registered."""
    registered = {mf.name for mf in REGISTRY.collect()}
    for name in (
        "db_connections_total",
        "db_reader_connections_total",
        "db_pool_active",
        "db_pool_idle",
        "db_pool_overflow",
        "db_pool_saturation_ratio",
        "db_pool_waiting",
    ):
        assert name in registered, f"{name} not found in registry"


def test_db_active_queries_inc_dec() -> None:
    """db_active_queries counter increments and decrements cleanly."""
    before = db_active_queries._value.get()
    db_active_queries.inc()
    assert db_active_queries._value.get() == before + 1
    db_active_queries.dec()
    assert db_active_queries._value.get() == before


def test_db_query_duration_observe() -> None:
    """db_query_duration_seconds histogram accepts observations."""
    before = db_query_duration_seconds.labels(pool="writer")._sum.get()
    db_query_duration_seconds.labels(pool="writer").observe(0.05)
    assert db_query_duration_seconds.labels(pool="writer")._sum.get() > before


def test_db_pool_active_labels() -> None:
    """db_pool_active gauge works with pool labels."""
    db_pool_active.labels(pool="writer").set(5)
    assert db_pool_active.labels(pool="writer")._value.get() == 5
    db_pool_active.labels(pool="reader").set(3)
    assert db_pool_active.labels(pool="reader")._value.get() == 3
