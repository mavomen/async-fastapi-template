"""Shared-kernel database models.

Domain-owned models live in their bounded contexts (app/identity/models/,
app/notifications/models/). This package holds only cross-context base
classes and models that have not been assigned to a context.
"""

from app.models.audit_log import AuditLog
from app.models.base import Base, BaseModel, SoftDeleteMixin, TimestampMixin
from app.models.category import (
    Category,
    Tag,
    cms_page_categories,
    cms_page_tags,
    cms_post_categories,
    cms_post_tags,
)
from app.models.file import File
from app.models.page import Page
from app.models.post import Post
from app.models.tenant_base import TenantBaseModel

__all__ = [
    "AuditLog",
    "Base",
    "BaseModel",
    "Category",
    "File",
    "Page",
    "Post",
    "SoftDeleteMixin",
    "Tag",
    "TenantBaseModel",
    "TimestampMixin",
    "cms_page_categories",
    "cms_page_tags",
    "cms_post_categories",
    "cms_post_tags",
]
