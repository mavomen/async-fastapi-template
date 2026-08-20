"""Prometheus metrics configuration and custom collectors."""

from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator, metrics

# Note: http_requests_total and http_request_duration_seconds are provided by
# prometheus_fastapi_instrumentator and must NOT be redeclared here.

active_requests = Gauge(
    "active_requests",
    "Number of currently active requests",
)

db_connections_total = Gauge(
    "db_connections_total",
    "Number of database connections in the writer pool",
)

db_reader_connections_total = Gauge(
    "db_reader_connections_total",
    "Number of database connections in the reader pool",
)

db_pool_saturation_ratio = Gauge(
    "db_pool_saturation_ratio",
    "Current pool saturation ratio (active/total) for each pool",
    ["pool"],
)

db_pool_active = Gauge(
    "db_pool_active",
    "Checked-out (in-use) connections per pool",
    ["pool"],
)

db_pool_idle = Gauge(
    "db_pool_idle",
    "Idle connections waiting in the pool",
    ["pool"],
)

db_pool_overflow = Gauge(
    "db_pool_overflow",
    "Connections beyond base pool_size (overflow)",
    ["pool"],
)

db_pool_waiting = Gauge(
    "db_pool_waiting",
    "In-flight checkout calls (proxy for waiter count)",
)

db_active_queries = Gauge(
    "db_active_queries",
    "Currently executing SQL queries across all pools",
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Duration of individual SQL queries in seconds",
    ["pool"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

cache_hits_total = Counter(
    "cache_hits_total",
    "Total number of cache hits",
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total number of cache misses",
)

rate_limit_blocked_total = Counter(
    "rate_limit_blocked_total",
    "Total number of requests blocked by rate limiter",
    ["tier", "endpoint"],
)

rate_limit_remaining = Gauge(
    "rate_limit_remaining",
    "Remaining requests in current rate limit window",
    ["tier"],
)

http_queries_per_request = Histogram(
    "http_queries_per_request",
    "Number of SQL queries per HTTP request",
    buckets=[0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000],
)

# Default instrumentator with standard metrics
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
    inprogress_name="http_requests_inprogress",
    inprogress_labels=False,
)

# Add standard metrics
instrumentator.add(
    metrics.request_size(
        should_include_handler=True,
        should_include_method=True,
        should_include_status=True,
    )
).add(
    metrics.response_size(
        should_include_handler=True,
        should_include_method=True,
        should_include_status=True,
    )
).add(
    metrics.latency(
        should_include_handler=True,
        should_include_method=True,
    )
).add(
    metrics.requests(
        should_include_handler=True,
        should_include_method=True,
        should_include_status=True,
    )
)
