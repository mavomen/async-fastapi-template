# Monitoring Setup Guide

The project includes **Prometheus** for metrics collection and **Grafana** for dashboards.

## Docker Compose

Additional services in `docker-compose.yml`:

- `prometheus` on port 9090
- `grafana` on port 3000 (admin/admin)

## Dashboards

Pre‑configured dashboards are in `monitoring/grafana/dashboards/`:

- **API Metrics** – requests, latency, in‑flight
- **Database Metrics** – connection pool
- **Cache Metrics** – hit rate

## Access

- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`

## Customising

Edit `monitoring/prometheus/prometheus.yml` to add or change scrape targets.

## Production

For production, set strong Grafana passwords and persist volumes.

## SQL Query Count

Every request includes an `X-Query-Count` response header showing the number of database queries executed. The metric `http_queries_per_request` (Prometheus histogram) records the distribution of query counts per request. Use this to identify N+1 query problems.

## Performance Regression CI

The CI pipeline runs benchmarks on every push to `main` and `develop`. If any benchmark becomes more than 20% slower than the stored baseline, the job fails. The baseline is automatically updated after a successful run.
