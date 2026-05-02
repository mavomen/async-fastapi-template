"""CRUD operations package."""

from app.crud.base import CRUDBase
from app.crud.user import user

__all__ = ["CRUDBase", "user"]
