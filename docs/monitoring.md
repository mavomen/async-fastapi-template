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
