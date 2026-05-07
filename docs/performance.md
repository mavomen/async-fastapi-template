# Performance Tuning Guide

## Profiling Middleware

Slow database queries (above `SLOW_QUERY_THRESHOLD_MS`, default 500ms) are logged automatically. To see them, check the `app.db` logger.

## Connection Pool Configuration

In `app/core/database.py`, the pool is tuned:

- `pool_size=20`
- `max_overflow=10`
- `pool_recycle=3600`

Adjust these via environment variables or directly in the code for your workload.

## Redis Pipelining

For batch operations, use the `batch_set` and `batch_get` utilities from `app/utils/redis_pipeline.py` to reduce round trips.

## Bulk Operations

Use the `POST /api/v1/users/bulk` endpoint to create multiple users in one request. This reduces network overhead and improves throughput.

## Benchmarking

Run micro-benchmarks with:

```sh
poetry run pytest benchmarks/
```

## Load Testing

Start Locust from the project root:

```sh
poetry run locust -f locustfile.py
```

Then open http://localhost:8089 and simulate traffic against your running API.

## Baseline Results

_Add your own results after running benchmarks and load tests._
