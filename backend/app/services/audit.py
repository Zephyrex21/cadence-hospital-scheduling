"""Audit logging helper.

``record_audit`` flushes but does not commit — the caller owns the transaction so
the audit row and the change it describes commit atomically together.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: str | int,
    action: str,
    actor_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        actor_id=actor_id,
        before=before,
        after=after,
        reason=reason,
    )
    db.add(entry)
    db.flush()
    return entry
