"""Billing bounded context (reserved).

This context is intentionally empty. It is reserved for future billing
capabilities — plans, subscriptions, invoices, usage metering, and
payment-provider integration.

Conventions for code that lands here:
- Domain-owned models in ``app/billing/models/`` (inherit from
  ``app.models.base`` / ``TenantBaseModel`` as appropriate).
- Pydantic schemas in ``app/billing/schemas/``, CRUD in
  ``app/billing/crud/``, services in ``app/billing/services/``,
  Celery tasks in ``app/billing/tasks/``, HTTP routers in
  ``app/billing/api/endpoints/``.
- Routers are mounted in ``app/api/__init__.py``; model modules must be
  imported in ``alembic/env.py`` so autogenerate sees the metadata.

Cross-context imports are allowed only at documented seams; see the
"Architecture / bounded contexts" section of docs/ARCHITECTURE.md.
"""
