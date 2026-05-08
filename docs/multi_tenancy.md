# Multi‑Tenancy Guide

The project supports multi‑tenancy with a **shared‑database + tenant‑id column** architecture.

## Tenant Model

- `Tenant` stores organisation info (`name`, `slug`).
- All tenant‑scoped models inherit from `TenantBaseModel` and contain a `tenant_id` foreign key.

## Row‑Level Security (RLS)

SQLAlchemy event listeners in `app/core/database.py` automatically:

- **SELECT** queries add `WHERE tenant_id = current_tenant`
- **INSERT** operations set `tenant_id` to the current tenant
- **UPDATE / DELETE** operations filter by tenant

This ensures complete data isolation between tenants without manual filter logic.

## Tenant Resolution

The `TenantMiddleware` in `app/middleware/tenant.py` resolves the tenant from:

1. `X‑Tenant‑ID` header (if numeric)
2. Fallback: first active tenant in the database

The resolved tenant ID is stored in a context variable for the duration of the request.

## Management Endpoints

Superusers can manage tenants via:

- `POST /api/v1/tenants/` – create a tenant
- `GET /api/v1/tenants/` – list all tenants

## Adding Tenant‑Scope to New Models

1. Inherit from `TenantBaseModel` instead of `BaseModel`.
2. Create an Alembic migration that adds `tenant_id` column.
3. Register the model in the admin dashboard.

The RLS events will automatically apply filter rules.
