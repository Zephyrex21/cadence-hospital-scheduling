"""Consultation service: the patient queue and doctor status transitions.

Status transitions are guarded (only valid moves allowed) and version-checked.
A doctor may only change their own appointments; an administrator may change any.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import (
    AppointmentStatus,
    AuditAction,
    ConsultationAction,
    Role,
)
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.appointment import Appointment
from app.models.base import ensure_aware_utc
from app.models.user import User
from app.scheduling.queue import QueueItem, compute_queue
from app.services.audit import record_audit

_ACTIVE = (
    AppointmentStatus.BOOKED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.IN_PROGRESS,
)

# action -> (allowed source statuses, target status)
_TRANSITIONS: dict[ConsultationAction, tuple[tuple[AppointmentStatus, ...], AppointmentStatus]] = {
    ConsultationAction.CHECK_IN: ((AppointmentStatus.BOOKED,), AppointmentStatus.CHECKED_IN),
    ConsultationAction.START: (
        (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN),
        AppointmentStatus.IN_PROGRESS,
    ),
    ConsultationAction.COMPLETE: ((AppointmentStatus.IN_PROGRESS,), AppointmentStatus.COMPLETED),
    ConsultationAction.NO_SHOW: (
        (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN),
        AppointmentStatus.NO_SHOW,
    ),
}


def _day_bounds(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def list_queue(db: Session, now: datetime, doctor_id: int | None = None) -> list[dict[str, Any]]:
    now = ensure_aware_utc(now)
    lo, hi = _day_bounds(now)
    stmt = select(Appointment).where(
        Appointment.status.in_(_ACTIVE),
        Appointment.scheduled_start < hi,
        Appointment.scheduled_end > lo,
    )
    if doctor_id is not None:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    appts = list(db.scalars(stmt))

    items = [
        QueueItem(
            appointment_id=a.id,
            doctor_id=a.doctor_id,
            scheduled_start=a.scheduled_start,
            scheduled_end=a.scheduled_end,
            status=a.status,
            acuity=a.acuity,
        )
        for a in appts
    ]
    entries = compute_queue(items, now)

    by_id = {a.id: a for a in appts}
    result: list[dict[str, Any]] = []
    for e in entries:
        a = by_id[e.appointment_id]
        result.append(
            {
                "appointment_id": e.appointment_id,
                "position": e.position,
                "est_wait_min": e.est_wait_min,
                "acuity": e.acuity.value,
                "status": e.status.value,
                "scheduled_start": e.scheduled_start.isoformat(),
                "patient": {"id": a.patient.id, "name": a.patient.name, "mrn": a.patient.mrn},
                "doctor": {"id": a.doctor.id, "name": a.doctor.name},
                "type_name": a.type.name,
            }
        )
    return result


def change_consultation_status(
    db: Session,
    appointment_id: int,
    action: ConsultationAction,
    *,
    actor: User,
    expected_version: int | None = None,
) -> Appointment:
    appt = db.get(Appointment, appointment_id, with_for_update={"of": Appointment})
    if appt is None:
        raise NotFoundError("Appointment not found")

    # A doctor may only manage their own consultations.
    if actor.role == Role.DOCTOR and appt.doctor_id != actor.id:
        raise ForbiddenError("You can only change your own appointments")

    allowed_from, target = _TRANSITIONS[action]
    if appt.status not in allowed_from:
        raise ConflictError(
            f"Cannot {action.value} an appointment that is {appt.status.value}",
            details={"code": "invalid_transition"},
        )
    if expected_version is not None and expected_version != appt.version:
        raise ConflictError("Appointment was modified by someone else; reload and retry")

    before = {"status": appt.status.value, "version": appt.version}
    appt.status = target
    appt.version += 1

    record_audit(
        db,
        entity_type="appointment",
        entity_id=appt.id,
        action=AuditAction.UPDATE,
        actor_id=actor.id,
        before=before,
        after={"status": appt.status.value, "version": appt.version},
        reason=action.value,
    )
    db.commit()
    db.refresh(appt)
    return appt
