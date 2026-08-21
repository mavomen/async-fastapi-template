"""Tests for domain restructuring: schema extraction, CRUD purity, orphan cleanup."""

from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# 1. Schema extraction – TenantCreate
# ---------------------------------------------------------------------------


class TestTenantSchemaExtracted:
    """TenantCreate moved from inline to app.identity.schemas.tenant."""

    def test_import_from_schemas(self) -> None:
        from app.identity.schemas.tenant import TenantCreate

        obj = TenantCreate(name="Acme", slug="acme")
        assert obj.name == "Acme"
        assert obj.slug == "acme"

    def test_slug_optional(self) -> None:
        from app.identity.schemas.tenant import TenantCreate

        obj = TenantCreate(name="Acme")
        assert obj.slug is None

    def test_re_import_from_endpoint_still_works(self) -> None:
        from app.identity.api.endpoints.tenants import TenantCreate

        obj = TenantCreate(name="X")
        assert obj.name == "X"

    def test_available_in_schemas_init(self) -> None:
        from app.identity.schemas import TenantCreate

        assert TenantCreate is not None


# ---------------------------------------------------------------------------
# 2. Schema extraction – IPRule schemas
# ---------------------------------------------------------------------------


class TestIPRuleSchemasExtracted:
    """IPRuleCreate/Update/Response moved from inline to app.identity.schemas.tenant_ip_rule."""

    def test_import_create(self) -> None:
        from app.identity.schemas.tenant_ip_rule import IPRuleCreate

        obj = IPRuleCreate(tenant_id=1, ip_or_cidr="10.0.0.0/8", action="allow")
        assert obj.tenant_id == 1
        assert obj.action == "allow"
        assert obj.priority == 0

    def test_import_update(self) -> None:
        from app.identity.schemas.tenant_ip_rule import IPRuleUpdate

        obj = IPRuleUpdate(action="deny")
        assert obj.action == "deny"
        assert obj.ip_or_cidr is None

    def test_import_response(self) -> None:
        from app.identity.schemas.tenant_ip_rule import IPRuleResponse

        obj = IPRuleResponse(
            id=1, tenant_id=1, ip_or_cidr="::1", action="allow", priority=0, description=None
        )
        assert obj.id == 1

    def test_create_invalid_action_rejected(self) -> None:
        from app.identity.schemas.tenant_ip_rule import IPRuleCreate

        with pytest.raises(ValidationError):
            IPRuleCreate(tenant_id=1, ip_or_cidr="10.0.0.0/8", action="invalid")

    def test_available_in_schemas_init(self) -> None:
        from app.identity.schemas import IPRuleCreate, IPRuleResponse, IPRuleUpdate

        assert IPRuleCreate is not None
        assert IPRuleUpdate is not None
        assert IPRuleResponse is not None

    def test_endpoint_imports_from_schemas(self) -> None:
        from app.identity.api.endpoints.tenant_ip_rules import IPRuleCreate as EpCreate
        from app.identity.schemas.tenant_ip_rule import IPRuleCreate as SchemaCreate

        assert EpCreate is SchemaCreate


# ---------------------------------------------------------------------------
# 3. CRUD purity – CRUDFile no longer imports thumbnail service
# ---------------------------------------------------------------------------


class TestCRUDFilePurity:
    """CRUDFile should not import any service modules (thumbnails, email, etc.)."""

    def test_no_thumbnail_import(self) -> None:
        import pathlib

        import app.crud.file as mod

        source = pathlib.Path(importlib.util.find_spec(mod.__name__).origin)  # type: ignore[arg-type]
        content = source.read_text()
        assert "from app.services.thumbnail" not in content
        assert "from app.services" not in content
        assert "import generate_all_thumbnails" not in content

    def test_create_from_upload_accepts_thumbnail_paths(self) -> None:
        from app.crud.file import CRUDFile
        from app.models.file import File

        crud = CRUDFile(File)
        # Verify the method signature includes thumbnail_paths
        import inspect

        sig = inspect.signature(crud.create_from_upload)
        assert "thumbnail_paths" in sig.parameters

    def test_create_from_upload_defaults_thumbnails_none(self) -> None:
        from app.crud.file import CRUDFile
        from app.models.file import File

        crud = CRUDFile(File)
        import inspect

        param = inspect.signature(crud.create_from_upload).parameters["thumbnail_paths"]
        assert param.default is None


# ---------------------------------------------------------------------------
# 4. Orphan cleanup – metrics.py removed
# ---------------------------------------------------------------------------


class TestMetricsOrphanRemoved:
    """app/api/endpoints/metrics.py should no longer exist."""

    def test_module_not_importable(self) -> None:
        import sys

        mod_name = "app.api.endpoints.metrics"
        # Remove from sys.modules if cached from prior import
        sys.modules.pop(mod_name, None)

        with pytest.raises((ModuleNotFoundError, ImportError)):
            importlib.import_module(mod_name)

    def test_file_not_exists(self) -> None:
        import pathlib

        metrics_file = pathlib.Path("app/api/endpoints/metrics.py")
        assert not metrics_file.exists()

    def test_not_registered_in_api_router(self) -> None:
        """metrics.router should not appear in api/__init__.py."""
        import pathlib

        init = pathlib.Path("app/api/__init__.py").read_text()
        assert "metrics" not in init


# ---------------------------------------------------------------------------
# 5. Endpoint functionality preserved
# ---------------------------------------------------------------------------


class TestTenantEndpointPreserved:
    """Tenant endpoint still works with extracted schema."""

    @pytest.mark.asyncio
    async def test_create_tenant_schema_validates(self) -> None:
        from app.identity.schemas.tenant import TenantCreate

        tc = TenantCreate(name="Test Org", slug="test-org")
        assert tc.model_dump() == {"name": "Test Org", "slug": "test-org"}

    @pytest.mark.asyncio
    async def test_list_tenants_endpoint_exists(self) -> None:
        from app.identity.api.endpoints.tenants import list_tenants

        assert callable(list_tenants)


class TestIPRuleEndpointPreserved:
    """IP rule endpoints still work with extracted schemas."""

    def test_create_ip_rule_endpoint_exists(self) -> None:
        from app.identity.api.endpoints.tenant_ip_rules import create_ip_rule

        assert callable(create_ip_rule)

    def test_list_ip_rules_endpoint_exists(self) -> None:
        from app.identity.api.endpoints.tenant_ip_rules import list_ip_rules

        assert callable(list_ip_rules)

    def test_get_ip_rule_endpoint_exists(self) -> None:
        from app.identity.api.endpoints.tenant_ip_rules import get_ip_rule

        assert callable(get_ip_rule)

    def test_update_ip_rule_endpoint_exists(self) -> None:
        from app.identity.api.endpoints.tenant_ip_rules import update_ip_rule

        assert callable(update_ip_rule)

    def test_delete_ip_rule_endpoint_exists(self) -> None:
        from app.identity.api.endpoints.tenant_ip_rules import delete_ip_rule

        assert callable(delete_ip_rule)


# ---------------------------------------------------------------------------
# 6. Model docstrings
# ---------------------------------------------------------------------------


class TestModelDocstrings:
    """Models should have class-level docstrings for documentation generation."""

    @pytest.mark.parametrize(
        "module_path,class_name",
        [
            ("app.identity.models.api_key", "ApiKey"),
            ("app.models.file", "File"),
            ("app.identity.models.tenant", "Tenant"),
            ("app.identity.models.tenant_ip_rule", "TenantIPRule"),
            ("app.identity.models.user", "User"),
            ("app.identity.models.role", "Role"),
            ("app.identity.models.role", "Permission"),
            ("app.models.notification", "Notification"),
            ("app.models.webhook", "Webhook"),
        ],
    )
    def test_class_has_docstring(self, module_path: str, class_name: str) -> None:
        import importlib

        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        assert cls.__doc__, f"{module_path}.{class_name} is missing a class docstring"


# ---------------------------------------------------------------------------
# 7. Schema consistency – backward compatibility
# ---------------------------------------------------------------------------


class TestSchemaBackwardCompatibility:
    """Existing code importing from endpoints still works; new canonical path also works."""

    def test_tenant_create_both_paths_same_class(self) -> None:
        from app.identity.api.endpoints.tenants import TenantCreate as Ep
        from app.identity.schemas.tenant import TenantCreate as Schema

        assert Ep is Schema

    def test_ip_rule_schemas_both_paths_same_class(self) -> None:
        from app.identity.api.endpoints.tenant_ip_rules import IPRuleCreate as EpCreate
        from app.identity.api.endpoints.tenant_ip_rules import IPRuleResponse as EpResp
        from app.identity.api.endpoints.tenant_ip_rules import IPRuleUpdate as EpUpdate
        from app.identity.schemas.tenant_ip_rule import IPRuleCreate as SchemaCreate
        from app.identity.schemas.tenant_ip_rule import IPRuleResponse as SchemaResp
        from app.identity.schemas.tenant_ip_rule import IPRuleUpdate as SchemaUpdate

        assert EpCreate is SchemaCreate
        assert EpUpdate is SchemaUpdate
        assert EpResp is SchemaResp
