# TODO — Phase III

> Phase II shipped complete in v3.5.0 (46/46 items): webhooks, notification inbox &
> preferences, k8s operator + hardening, chaos engineering CI, bounded-context
> restructure, and everything listed in CHANGELOG.
>
> Phase III focuses on three themes — **billing**, **event reliability**, and
> **compliance** — plus net-new fill-out work across the existing sections.
> Everything below is net-new; nothing duplicates shipped features.

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

## 💰 Billing

Implements the reserved `app/billing/` scaffold (see docs/ARCHITECTURE.md bounded
contexts). All billing models/schemas/crud/services/tasks/endpoints live inside the
context; routers mount via `app/api/__init__.py`; model modules register in
`alembic/env.py`.

**`feat/billing-plans-subscriptions`** ✅
- Plan and subscription models in `app/billing/models/` (tenant-scoped via TenantBaseModel)
- Lifecycle states: trial → active → past_due → canceled, with state-machine transitions
- Plan changes with proration logic (upgrades immediate + credit, downgrades at period end)
- REST endpoints under `/api/v1/billing/` (plans catalog + subscriptions lifecycle)

**`feat/billing-stripe-integration`** ✅ done (2026-08-24)
- Stripe customer sync per tenant/user
- Checkout sessions for plan purchase and upgrades
- Inbound Stripe webhook endpoint with signature verification
- Idempotent event processing (safe against Stripe retries)

**`feat/billing-invoicing`** ✅ done (2026-08-24)
- Invoice generation from subscription periods
- ~~PDF rendering~~ deferred — invoice row + line items are the document of record; binary rendering lands with a later item
- Invoice list/detail API with tax/VAT fields

**`feat/billing-usage-metering`** ✅ done
- Usage counters (Redis-backed) for metered dimensions — period-scoped keys, TTL with grace, fail-open reads/writes
- Metered line items rolled into invoices — overage-only billing (`max(0, used - included)` × unit price)
- Quota enforcement as a router-level dependency on authenticated v1 routes (429 over quota), gated behind `BILLING_QUOTA_ENABLED`; `GET /billing/subscriptions/usage` endpoint

**`feat/billing-dunning`** ✅ done
- Payment retry schedule with exponential backoff — position counter advanced by real failures (Stripe webhooks) and due sweep ticks alike; delay = base * 2**(N-1), capped at 7 days
- Grace periods and automated account suspension — sweep runs every 15 min; suspension is a new terminal `suspended` status (distinct from user-initiated cancel)
- Dunning emails through the notifications context — `billing.dunning.payment_failed/payment_reminder/suspended/recovered` events fan out to all active tenant users; channel gating applies

**`feat/billing-admin-ui`** ✅ done
- HTMX admin views: subscriptions, invoices, payment history
- Manual plan override and refund trigger actions
- Admin action routes: `POST /admin/subscriptions/{id}/override-plan` (validated active-plan swap resetting the billing period), `POST /admin/subscriptions/{id}/set-status` (transition-validated, updates dunning bookkeeping), `POST /admin/invoices/{id}/refund` (real Stripe refund via `create_refund`, 503 when unconfigured, `pi_`/`charge_` references); `actions_row.html` fragment with hx-post buttons rendered on detail pages for tables that declare actions

---

## 📨 Event Reliability

Closes the at-least-once gaps in the existing event bus (`app/events/`) and Celery
delivery paths.

**`feat/transactional-outbox`** ⏳ open
- Outbox table written in the same transaction as domain changes
- Relay worker publishes to the EventBus after commit — no lost events on crash
- Per-aggregate ordering guarantees

**`feat/idempotency-keys`** ⏳ open
- `Idempotency-Key` header support for POST/PATCH endpoints
- Stored responses replayed for duplicate keys
- 409 Conflict when key is reused with a different payload

**`feat/consumer-inbox`** ⏳ open
- Inbox table deduplicating processed event IDs
- Effectively-once handlers for bus consumers and webhook deliveries

**`ops/event-replay-cli`** ⏳ open
- CLI to replay events by topic/timeframe into a target environment
- Dry-run mode with diff preview before actual replay

**`obs/event-lag-monitoring`** ⏳ open
- Consumer lag metrics for bus consumers and Celery queues
- Alert rules + Grafana panel for lag thresholds

---

## 🔐 Security & Compliance

**`sec/gdpr-data-toolkit`** ⏳ open
- Self-service data export: machine-readable JSON archive of a user's data
- Erasure request workflow with anonymisation job (reuses `cli anonymise-db` logic)
- Admin queue for reviewing/approving erasure requests

**`sec/retention-policies`** ⏳ open
- Configurable retention windows per data class (audit logs, notifications, files)
- Scheduled purge tasks wired into Celery beat
- Legal-hold flag exempting records from purge

**`sec/audit-hash-chain`** ⏳ open
- Tamper-evident audit log: per-tenant hash chaining of audit entries
- Periodic chain anchoring and a verification CLI command

**`sec/siem-streaming`** ⏳ open
- Stream auth/audit events to SIEM sinks (Splunk/Elastic HTTP JSON endpoints)
- Configurable sink URL, batching, and failure buffering

**`sec/consent-management`** ⏳ open
- Versioned consent records (ToS, marketing) with timestamped acceptance
- Consent enforcement hooks in the notifications email channel gating

**`test/tenant-isolation-fuzz`** ⏳ open
- Automated fuzzer asserting zero cross-tenant reads/writes across all endpoints
- RLS bypass detection: every endpoint exercised under two tenants with swapped tokens

**`ops/sbom-supply-chain`** ⏳ open
- CycloneDX SBOM generated per container image in CI
- SLSA provenance attestation; sample sigstore policy-controller admission config

---

## 🗄️ Database & Storage

**`perf/table-partitioning`** ⏳ open
- Declarative monthly range partitions for `audit_logs` and high-volume event tables
- Automated partition rotation and retention-aware detach/drop
- Migration guide for existing deployments

**`perf/pgbouncer-k8s`** ⏳ open
- PgBouncer deployment added to Helm chart (transaction pooling mode)
- Pooler-aware SQLAlchemy settings per environment

---

## ⚡ Performance

**`perf/etag-caching`** ⏳ open
- ETag / If-None-Match support on GET collection endpoints
- 304 Not Modified responses to cut payload costs

**`perf/cache-single-flight`** ⏳ open
- Single-flight locking so concurrent cache misses trigger one backend query
- Thundering-herd protection for hot keys

---

## 📡 Observability

**`obs/continuous-profiling`** ⏳ open
- Pyroscope agent wired into the app image (env-gated, off by default)
- Flamegraph dashboards linked from latency alert rules

*(event-lag monitoring lives under 📨 Event Reliability)*

---

## ☸️ Infrastructure & Deployment

**`ops/vault-secrets`** ⏳ open
- External Secrets Operator integration with Vault provider
- Migration path off Helm-placeholder secrets for production installs

**`ops/ws-presence-scale`** ⏳ open
- Redis-backed WebSocket presence and channel fan-out across replicas
- Multi-worker chat scale-out with connection draining on shutdown

*(SBOM/supply-chain lives under 🔐 Security & Compliance)*

---

## 🛠️ Developer Experience

**`dx/project-generator`** ⏳ open
- Copier template to instantiate downstream projects from this template
- Interactive rename, module selection (billing/CMS/webhooks optional), secret generation

**`dx/devcontainer`** ⏳ open
- Devcontainer with prebuilt services image (Postgres, Redis, Kafka)
- Preinstalled toolchain: poetry, pre-commit hooks ready, task runner defaults

---

## 🧪 Testing & Quality Gates

**`test/soak-nightly`** ⏳ open
- Nightly 2h low-VU soak profile (k6) detecting memory leaks and connection drift
- Trend report comparing RSS/pool metrics across runs; fail on sustained growth
