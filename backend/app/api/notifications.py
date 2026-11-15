"""Patient notification outbox: who was told their appointment moved, and retrying failures."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.enums import Role
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.user import User
from app.schemas.notification import NotificationOut, NotificationPatient
from app.services.notifications import list_notifications, mask_phone, retry_notification

router = APIRouter(tags=["notifications"])

NOTIFY_ROLES = (Role.RECEPTIONIST, Role.TRIAGE_NURSE, Role.ADMINISTRATOR)


def _out(n: Notification, p: Patient) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        created_at=n.created_at,
        sent_at=n.sent_at,
        kind=n.kind,
        channel=n.channel,
        provider=n.provider,
        recipient=mask_phone(n.recipient),
        body=n.body,
        status=n.status,
        error=n.error,
        attempts=n.attempts,
        appointment_id=n.appointment_id,
        decision_id=n.decision_id,
        patient=NotificationPatient(id=p.id, name=p.name, mrn=p.mrn),
    )


@router.get("/notifications", response_model=list[NotificationOut])
def get_notifications(
    status: Literal["queued", "sent", "failed", "skipped"] | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*NOTIFY_ROLES)),
) -> list[NotificationOut]:
    return [_out(n, p) for n, p in list_notifications(db, status=status, limit=limit)]


@router.post("/notifications/{notification_id}/retry", response_model=NotificationOut)
def retry(
    notification_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*NOTIFY_ROLES)),
) -> NotificationOut:
    row = retry_notification(db, notification_id)
    patient = db.get(Patient, row.patient_id)
    assert patient is not None
    return _out(row, patient)
