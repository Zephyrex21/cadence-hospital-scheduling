"""Audit trail tests."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.audit import AuditLog
from app.models.user import User


def test_registering_patient_writes_audit_row(
    client: TestClient,
    db_session: Session,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    recep = user_factory(Role.RECEPTIONIST)
    resp = client.post(
        "/patients",
        json={"name": "Jane Doe", "date_of_birth": "1990-06-15", "sex": "female"},
        headers=auth_headers(recep),
    )
    patient_id = resp.json()["id"]

    entry = db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_type == "patient", AuditLog.entity_id == str(patient_id)
        )
    )
    assert entry is not None
    assert entry.action == "create"
    assert entry.actor_id == recep.id
    assert entry.after is not None and entry.after["name"] == "Jane Doe"
