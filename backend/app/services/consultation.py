"""Consultation service: the patient queue and doctor status transitions.

Status transitions are guarded (only valid moves allowed) and version-checked.
A doctor may only change their own appointments; an administrator may change any.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import clinic_day_bounds
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
from app.services.locking import lock_doctors

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


def list_queue(db: Session, now: datetime, doctor_id: int | None = None) -> list[dict[str, Any]]:
    now = ensure_aware_utc(now)
    lo, hi = clinic_day_bounds(now)
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


# Who may perform each action. Arrival and no-show are front-desk tasks; starting and
# completing a consultation are clinical. (A doctor is further limited to their own patients.)
_FRONT_DESK = {Role.RECEPTIONIST, Role.TRIAGE_NURSE, Role.DOCTOR, Role.ADMINISTRATOR}
_CLINICAL = {Role.DOCTOR, Role.ADMINISTRATOR}
_ACTION_ROLES: dict[ConsultationAction, set[Role]] = {
    ConsultationAction.CHECK_IN: _FRONT_DESK,
    ConsultationAction.NO_SHOW: _FRONT_DESK,
    ConsultationAction.START: _CLINICAL,
    ConsultationAction.COMPLETE: _CLINICAL,
}


def change_consultation_status(
    db: Session,
    appointment_id: int,
    action: ConsultationAction,
    *,
    actor: User,
    expected_version: int | None = None,
) -> Appointment:
    if actor.role not in _ACTION_ROLES[action]:
        raise ForbiddenError(f"Your role cannot {action.value.replace('_', ' ')} a patient")

    peek = db.get(Appointment, appointment_id)
    if peek is None:
        raise NotFoundError("Appointment not found")
    if action == ConsultationAction.START:
        # Same lock order as the emergency flow (doctor lock first, then the row), so two
        # simultaneous "start" clicks can't both pass the one-at-a-time check below.
        lock_doctors(db, [peek.doctor_id])
    appt = db.get(
        Appointment, appointment_id, with_for_update={"of": Appointment}, populate_existing=True
    )
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

    if action == ConsultationAction.START:
        busy = db.scalar(
            select(Appointment.id).where(
                Appointment.doctor_id == appt.doctor_id,
                Appointment.status == AppointmentStatus.IN_PROGRESS,
                Appointment.id != appt.id,
            ).limit(1)
        )
        if busy is not None:
            raise ConflictError(
                "This doctor already has a consultation in progress. Complete it first.",
                details={"code": "consultation_in_progress"},
            )

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
