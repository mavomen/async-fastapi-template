# TODO — Phase II

> Items already shipped in the current template have been removed (SSE, full-text search,
> feature flags, scaffolding CLI, OTel tracing, Grafana dashboards, slowapi rate limiting,
> CSV/Excel export, Redis caching, K8s + Helm, Celery, audit logging, WebAuthn, email
> verification, security headers, outgoing webhooks, notification preferences). Everything
> below is net-new work.

---

## Branch conventions

| Prefix | When to use |
|--------|-------------|
| `feat/` | User-facing capability |
| `perf/` | Throughput, latency, resource usage |
| `sec/` | Auth hardening, secrets, access control |
| `obs/` | Metrics, tracing, alerting, dashboards |
| `ops/` | Infra, deployment, Kubernetes, cloud |
| `dx/` | Developer tooling, local dev, CI ergonomics |
| `test/` | Test coverage, strategies, automation |
| `refactor/` | Internal restructuring with no behavior change |
| `fix/` | Bug patches |

---

## 🗄️ Database & Storage

**`perf/db-read-write-split`** ✅
- Route reads to asyncpg replica pool, writes to primary
- Asyncpg pool min/max tuning per environment via config
- Alert when pool saturation exceeds 80%
- Expose active/idle/waiting connections as Prometheus gauges

**`perf/db-query-optimization`** ✅
- Keyset (cursor) pagination for high-traffic endpoints
- Auto-capture `EXPLAIN ANALYZE` when a query exceeds a configurable threshold
- Materialized views or Redis sorted sets for expensive aggregations
- Bulk insert/update for CSV import and audit log writes

**`ops/db-backup-automation`** ✅
- `pg_dump` to S3 on a schedule with 30-day retention
- Automated restore drill in CI

---

## ⚡ Performance

**`perf/redis-rate-limiting`** ✅
- Replace slowapi with a Redis sliding-window counter
- Per-endpoint rate limit tiers (public / authenticated / admin)
- Expose `X-RateLimit-Remaining` and related headers to API consumers

**`perf/response-compression`** ✅
- Brotli/gzip middleware for API responses
- 20 tests

**`perf/http-connection-pooling`** ✅
- Shared httpx.AsyncClient singleton with keep-alive connection pool
- OAuth2 `exchange_code` and `get_user_info` use shared client instead of per-call clients
- Lazy-load heavy modules: webauthn (app/auth), aioboto3 (app/storage/s3), openpyxl (app/utils/export_excel), kafka-python (app/events/kafka_bus)
- 7 tests for HttpClient lifecycle

**`perf/cdn-static-assets`** ✅
- `CDN_DOMAIN` setting + `get_url()` on `StorageBackend` / `S3Storage`
- Upload endpoints return optional `url` field when CDN is configured
- 5 tests for CDN URL generation with and without CDN domain, plus special-character encoding

---

## 🔐 Security

**`sec/oauth2-social-login`** ✅
- Google, GitHub, and GitLab OAuth2 providers
- Account linking for users who sign up with multiple providers
- 29 tests

**`sec/totp-2fa`** ✅
- Time-based one-time passwords (TOTP)
- Recovery code generation and storage
- 40 tests

**`sec/session-management`** ✅
- List active sessions per user in the API and admin UI
- Force-logout individual sessions
- 15 tests

**`sec/api-key-auth`** ✅
- Service-to-service API keys with scoped RBAC permissions
- 16 tests

**`sec/passwordless-magic-links`** ✅
- Email-based login with short-lived signed tokens (distinct from WebAuthn)
- 10 tests

**`sec/access-control`** ✅
- IP allow/deny list middleware per tenant
- Brute-force account lockout after N failed attempts
- Audit trail entries for auth events (login, MFA enrollment, password change)
- 17 tests

**`sec/jwt-hardening`** ✅
- JWT revocation list (blacklist compromised tokens before expiry)
- Secrets rotation endpoint — rotate `SECRET_KEY` and re-sign active JWTs
- 7 tests

**`sec/csp-headers`** ✅
- Strict Content Security Policy with `report-uri` endpoint
- 5 tests

---

## 📡 Observability

**`obs/distributed-tracing`** ✅
- Complete Grafana Tempo ingestion for the existing OTel spans

**`obs/slo-dashboards`** ✅
- Prometheus recording rules for SLO burn rates (5m/30m) and latency percentiles
- SLO Grafana dashboard: availability % gauge, p50/p95/p99 latency, error budget burn rate, 5xx rate
- Added db_active_queries + db_query_duration_seconds metrics (fixed broken DB dashboard)
- Removed duplicate http_requests_total / http_request_duration_seconds from metrics.py

**`obs/alerting`** ✅
- Prometheus alert rules: HighErrorRate, HighLatencyP99, DBPoolSaturated, RedisDown, PostgresDown, ErrorBudgetBurnFast/Slow
- Alertmanager with severity-based routing to Slack and PagerDuty
- /health/ready and /health/dependencies now check event bus (Redis or Kafka)
- SLACK_WEBHOOK_URL and PAGERDUTY_KEY config fields

**`obs/synthetic-monitoring`** ✅
- k6 smoke test (1 VU, 30s) and load test (10-50 VU ramp, 5min) in benchmarks/k6/
- Monthly CI workflow with pass/fail thresholds and benchmark trend reports
- Fixed compare_benchmarks.py to actually fail on >20% regression

**`obs/log-sampling`** ✅
- Adaptive sampling for high-throughput endpoints
- Full capture retained for errors

**`obs/error-catalog`** ✅
- Unique error codes in responses with links to internal playbooks

---

## 🚀 New Features

**`feat/webhook-engine`** ✅
- Outgoing webhooks for domain events
- Retry with exponential backoff and HMAC signature verification
- Delivery history, per-webhook management endpoints, and ping/test endpoint

**`feat/cms-module`**
- Markdown pages with version history and draft/publish workflow

**`feat/file-thumbnailing`** ✅
- Automatic thumbnail generation for uploaded images

**`feat/i18n`**
- Locale support for API error messages and email templates

**`feat/notification-preferences`** ✅
- Per-user opt-in/opt-out for email, in-app, and webhook channels
- Persisted in-app inbox with list/mark-read/mark-all-read/delete endpoints and WebSocket push
- Channel gating in the event-bus dispatcher, including actor-level webhook suppression

**`feat/soft-delete`** ✅
- Soft-delete pattern with restore endpoint and configurable auto-purge

---

## ☸️ Infrastructure & Deployment

**`ops/k8s-autoscaling`**
- Horizontal Pod Autoscaler based on request concurrency and CPU/memory
- Graceful shutdown handling for preemptible / spot instances

**`ops/k8s-operator`**
- Kubernetes operator to manage the app stack via CRDs

**`ops/k8s-hardening`**
- Network policies for micro-segmentation per service
- cosign image signing for supply chain security

**`ops/terraform-module`**
- Reusable Terraform module for the full stack (DB, Redis, Kafka, app)
- Cost allocation tags propagated to all cloud resources

**`ops/canary-deployments`**
- Flagger or Argo Rollouts with metric-based promotion gates

**`ops/multi-region-failover`**
- Active-passive region configuration with DNS failover

**`ops/chaos-engineering`**
- Chaos Mesh / Litmus scenarios for resilience testing on staging
- Weekly automated chaos experiments as a CI job

---

## 🛠️ Developer Experience

**`dx/domain-restructure`**
- Split `app/` into bounded contexts: `identity/`, `billing/`, `notifications/`

**`dx/local-dev`** ✅
- `docker compose up` provisions everything in under 10 seconds
- Celery auto-restart on code changes in dev (live reload for workers)
- Hot-reloadable Jinja2 templates in the admin dashboard

**`dx/pre-commit-expansion`** ✅
- Add `poetry check`, `pip-audit`, and `detect-secrets` hooks

**`dx/openapi-sdk-generation`**
- Auto-publish typed client SDKs for Python and TypeScript from the OpenAPI schema

**`dx/api-versioning`** ✅
- Formal `Accept: application/vnd.app.v2+json` header strategy
- Auto-detect breaking OpenAPI changes in CI and post a diff on PRs

**`dx/mypy-stubs`** ✅
- Generate mypy stub files for untyped third-party dependencies

---

## 🧪 Testing & Quality Gates

**`test/e2e-playwright`**
- Full admin dashboard flows via Playwright in CI

**`test/fuzz-and-contract`**
- schemathesis fuzz testing against staging
- Pact-style consumer-driven contract tests

**`test/performance-budgets`** ✅
- Fail CI if p95 latency exceeds a configured threshold
- k6 regression suite compared against a stored baseline
- Block deploys if SLO error budget is exhausted

**`test/mutation-coverage`** ✅
- Expand mutmut mutation testing scope
- Publish test coverage badge to README via CI
- Migration smoke tests against a throwaway DB in CI

**`test/security-scanning`** ✅
- `bandit` + `safety` + Trivy as mandatory CI gates
- Dependency vulnerability scanning via `poetry audit`
- Weekly automated dependency update PRs (Dependabot-style)

**`test/smoke-pipeline`** ✅
- Post-deploy smoke suite with canary detection
- Slack PR bot: auto-post lint score, coverage delta, and perf impact
