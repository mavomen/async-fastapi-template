"""Prometheus metrics configuration and custom collectors."""

from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator, metrics

# Custom application metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

active_requests = Gauge(
    "active_requests",
    "Number of currently active requests",
)

db_connections_total = Gauge(
    "db_connections_total",
    "Number of database connections in the pool",
)

cache_hits_total = Counter(
    "cache_hits_total",
    "Total number of cache hits",
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total number of cache misses",
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
