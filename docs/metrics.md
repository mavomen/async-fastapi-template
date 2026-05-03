# Metrics Guide

The project uses **Prometheus** for application metrics, exposed via `prometheus-fastapi-instrumentator` and custom collectors.

## Endpoint
- **`/metrics`** – Prometheus scraping endpoint (text/plain).

## Built‑in Metrics
- HTTP request count, latency, request/response size.
- In‑progress requests.

## Custom Metrics
- `db_connections_total` – current number of DB connections.
- `cache_hits_total` / `cache_misses_total` – cache hit/miss counters.
- `http_requests_total`, `http_request_duration_seconds`, `active_requests`.

## Usage
- Import and increment custom counters in your code as needed.
- The instrumentator is configured in `app/core/metrics.py` and attached in `main.py`.

## Viewing
Start Prometheus (or the included Docker setup) pointing to `http://<host>:8000/metrics`.
