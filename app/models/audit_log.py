"""Audit log model for tracking mutations."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AuditLog(BaseModel):
    """Records every create/update/delete with actor and changed fields."""

    __tablename__ = "audit_logs"

    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # INSERT, UPDATE, DELETE
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changed_fields: Mapped[str | None] = mapped_column(String, nullable=True)
    old_values: Mapped[str | None] = mapped_column(String, nullable=True)
    new_values: Mapped[str | None] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog(table={self.table_name}, action={self.action}, id={self.id})>"


def _get_changed_fields(connection: Any, target: Any, action: str) -> dict[str, str]:
    """Return a dict of changed fields and their old/new values."""
    import json

    state = target._sa_instance_state
    if action == "delete":
        old = {c.key: getattr(target, c.key) for c in target.__table__.columns}
        return {"old_values": json.dumps(old, default=str)}
    if action == "insert":
        new = {c.key: getattr(target, c.key) for c in target.__table__.columns}
        return {"new_values": json.dumps(new, default=str)}
    # update
    changes: dict[str, str] = {}
    old_vals = {}
    new_vals = {}
    for attr in state.attrs:
        hist = attr.load_history()
        if hist.has_changes():
            old_vals[attr.key] = hist.deleted[0] if hist.deleted else None
            new_vals[attr.key] = hist.added[0] if hist.added else None
    return {
        "old_values": json.dumps(old_vals, default=str),
        "new_values": json.dumps(new_vals, default=str),
    }


def install_audit_log_listener(target_model: Any) -> None:
    """Register before_flush listeners for a model to capture audit logs."""

    @event.listens_for(target_model, "before_insert", propagate=True)
    def _before_insert(mapper: Any, connection: Any, target: Any) -> None:
        connection.execute(
            AuditLog.__table__.insert().values(  # type: ignore[attr-defined]
                table_name=target.__tablename__,
                record_id=target.id,
                action="INSERT",
                actor_id=getattr(target, "_audit_actor_id", None),
                **_get_changed_fields(connection, target, "insert"),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

    @event.listens_for(target_model, "before_update", propagate=True)
    def _before_update(mapper: Any, connection: Any, target: Any) -> None:
        connection.execute(
            AuditLog.__table__.insert().values(  # type: ignore[attr-defined]
                table_name=target.__tablename__,
                record_id=target.id,
                action="UPDATE",
                actor_id=getattr(target, "_audit_actor_id", None),
                **_get_changed_fields(connection, target, "update"),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

    @event.listens_for(target_model, "before_delete", propagate=True)
    def _before_delete(mapper: Any, connection: Any, target: Any) -> None:
        connection.execute(
            AuditLog.__table__.insert().values(  # type: ignore[attr-defined]
                table_name=target.__tablename__,
                record_id=target.id,
                action="DELETE",
                actor_id=getattr(target, "_audit_actor_id", None),
                **_get_changed_fields(connection, target, "delete"),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
