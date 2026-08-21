"""IP allow/deny access control middleware per tenant."""

from collections.abc import Awaitable, Callable
from ipaddress import ip_address, ip_network

from fastapi import Request
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.tenant import get_current_tenant
from app.identity.models.tenant_ip_rule import TenantIPRule


def _parse_forwarded_for(request: Request) -> str | None:
    """Extract the real client IP from X-Forwarded-For or fallback to request.client."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _ip_matches_rule(client_ip: str, rule: TenantIPRule) -> bool:
    """Check if a client IP matches a single rule (supports CIDR)."""
    try:
        if "/" in rule.ip_or_cidr:
            return ip_address(client_ip) in ip_network(rule.ip_or_cidr)
        return ip_address(client_ip) == ip_address(rule.ip_or_cidr)
    except ValueError:
        return False


class TenantIPAccessMiddleware(BaseHTTPMiddleware):
    """Restrict access to routes based on per-tenant IP allow/deny rules.

    Ordering:
      1. No rules for the tenant → allow.
      2. Matching deny rule → 403.
      3. No matching allow rule → 403.
      4. Matching allow rule (and no matching deny) → allow.
    """

    async def dispatch(  # noqa: PLR0911
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if settings.ENVIRONMENT == "test":
            return await call_next(request)

        tenant_id = get_current_tenant()
        if tenant_id is None:
            return await call_next(request)

        client_ip = _parse_forwarded_for(request)
        if not client_ip:
            return await call_next(request)

        from app.core.database import sessionmanager

        async with sessionmanager.session() as db:
            result = await db.execute(
                select(TenantIPRule)
                .where(TenantIPRule.tenant_id == tenant_id)
                .order_by(TenantIPRule.priority.desc())
            )
            rules: list[TenantIPRule] = list(result.scalars().all())

        if not rules:
            return await call_next(request)

        matched_deny = any(_ip_matches_rule(client_ip, r) for r in rules if r.action == "deny")
        matched_allow = any(_ip_matches_rule(client_ip, r) for r in rules if r.action == "allow")

        if matched_deny:
            return Response("Access denied by IP rule", status_code=403)

        if not matched_allow:
            return Response("Access denied by IP rule", status_code=403)

        return await call_next(request)
