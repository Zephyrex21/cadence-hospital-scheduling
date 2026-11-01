"""Scheduling service: booking, cancellation, and schedule/slot reads.

Enforces the Phase 2 invariants server-side (the client cannot be trusted):
  * an appointment must fit entirely within one of the doctor's shifts;
  * it must not overlap another active appointment for that doctor.

Concurrency: ``book_appointment`` serialises writers per doctor (advisory lock on
PostgreSQL) and the database itself refuses overlapping active appointments for a
doctor or a patient (exclusion constraint / trigger — see ``models.overlap_guard``),
so two concurrent bookings can never both succeed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import clinic_day_bounds
from app.core.enums import AppointmentOrigin, AppointmentStatus, AuditAction
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.base import ensure_aware_utc, utcnow
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.user import User
from app.scheduling.availability import Interval, fits_in_any, generate_slots, has_conflict
from app.schemas.scheduling import AppointmentCreate
from app.services.audit import record_audit
from app.services.locking import lock_doctors

# Statuses that still occupy a doctor's time (used for conflict detection).
ACTIVE_STATUSES = (
    AppointmentStatus.BOOKED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.IN_PROGRESS,
)


def _shift_intervals(db: Session, doctor_id: int, lo: datetime, hi: datetime) -> list[Interval]:
    rows = db.scalars(
        select(Shift).where(
            Shift.doctor_id == doctor_id, Shift.start_utc < hi, Shift.end_utc > lo
        )
    )
    return [Interval(s.start_utc, s.end_utc) for s in rows]


def _busy_intervals(
    db: Session, doctor_id: int, lo: datetime, hi: datetime, *, for_update: bool = False
) -> list[tuple[int, Interval]]:
    stmt = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.status.in_(ACTIVE_STATUSES),
        Appointment.scheduled_start < hi,
        Appointment.scheduled_end > lo,
    )
    if for_update:
        stmt = stmt.with_for_update(of=Appointment)
    return [(a.id, Interval(a.scheduled_start, a.scheduled_end)) for a in db.scalars(stmt)]


def _patient_busy_intervals(
    db: Session, patient_id: int, lo: datetime, hi: datetime
) -> list[Interval]:
    """A patient's own active appointments (across all doctors) in [lo, hi)."""
    rows = db.scalars(
        select(Appointment).where(
            Appointment.patient_id == patient_id,
            Appointment.status.in_(ACTIVE_STATUSES),
            Appointment.scheduled_start < hi,
            Appointment.scheduled_end > lo,
        )
    )
    return [Interval(a.scheduled_start, a.scheduled_end) for a in rows]


def list_doctors(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(User, DoctorProfile)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .order_by(User.name)
    ).all()
    return [
        {"id": u.id, "name": u.name, "specialty": p.specialty} for u, p in rows
    ]


def list_appointment_types(db: Session) -> list[AppointmentType]:
    return list(db.scalars(select(AppointmentType).order_by(AppointmentType.name)))


def list_shifts(db: Session, doctor_id: int, day: datetime) -> list[Shift]:
    day = ensure_aware_utc(day)
    lo, hi = clinic_day_bounds(day)
    return list(
        db.scalars(
            select(Shift).where(
                Shift.doctor_id == doctor_id, Shift.start_utc < hi, Shift.end_utc > lo
            )
        )
    )


def available_slots(db: Session, doctor_id: int, type_id: int, day: datetime) -> list[Interval]:
    day = ensure_aware_utc(day)
    appt_type = db.get(AppointmentType, type_id)
    if appt_type is None:
        raise NotFoundError("Appointment type not found")
    lo, hi = clinic_day_bounds(day)
    shifts = _shift_intervals(db, doctor_id, lo, hi)
    # Shifts can straddle the day boundary; look at busy time across their full extent.
    busy_lo = min((s.start for s in shifts), default=lo)
    busy_hi = max((s.end for s in shifts), default=hi)
    busy = [iv for _, iv in _busy_intervals(db, doctor_id, busy_lo, busy_hi)]
    slots = generate_slots(shifts, busy, appt_type.default_duration_min)
    # Never offer a slot that has already started — the clock moves while the
    # page is open, so a slot valid at render can be in the past at booking.
    now = utcnow()
    return [s for s in slots if s.start >= now]


def list_schedule(db: Session, day: datetime, doctor_id: int | None = None) -> list[Appointment]:
    day = ensure_aware_utc(day)
    lo, hi = clinic_day_bounds(day)
    stmt = select(Appointment).where(
        Appointment.scheduled_start < hi,
        Appointment.scheduled_end > lo,
        Appointment.status != AppointmentStatus.CANCELLED,
    )
    if doctor_id is not None:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    return list(db.scalars(stmt.order_by(Appointment.doctor_id, Appointment.scheduled_start)))


def book_appointment(db: Session, data: AppointmentCreate, *, actor_id: int) -> Appointment:
    patient = db.get(Patient, data.patient_id)
    if patient is None:
        raise NotFoundError("Patient not found")
    appt_type = db.get(AppointmentType, data.type_id)
    if appt_type is None:
        raise NotFoundError("Appointment type not found")
    doctor = db.get(User, data.doctor_id)
    if doctor is None or db.get(DoctorProfile, data.doctor_id) is None:
        raise NotFoundError("Doctor not found")

    start = ensure_aware_utc(data.scheduled_start)
    end = start + timedelta(minutes=appt_type.default_duration_min)
    candidate = Interval(start, end)

    # Cannot book into the past.
    if start < utcnow():
        raise ValidationError(
            "Cannot book an appointment in the past",
            details={"code": "past_time"},
        )

    # Serialise concurrent writers for this doctor *before* reading, so a second
    # request re-reads the schedule after the first committed.
    lock_doctors(db, [data.doctor_id])

    # Look at the candidate's own time range (not a UTC calendar day): a booking
    # near midnight must still see appointments just across the boundary.
    shifts = _shift_intervals(db, data.doctor_id, start, end)
    if not fits_in_any(candidate, shifts):
        raise ValidationError("Requested time is outside the doctor's availability")

    # The patient cannot be in two places at once — reject an overlap with any of
    # their own active appointments (across every doctor), not just this doctor's.
    if has_conflict(candidate, _patient_busy_intervals(db, data.patient_id, start, end)):
        raise ConflictError(
            "The patient already has an appointment overlapping that time",
            details={"code": "patient_overlap"},
        )

    busy = [iv for _, iv in _busy_intervals(db, data.doctor_id, start, end, for_update=True)]
    if has_conflict(candidate, busy):
        raise ConflictError("That time slot is no longer available")

    appointment = Appointment(
        patient_id=data.patient_id,
        doctor_id=data.doctor_id,
        type_id=data.type_id,
        scheduled_start=start,
        scheduled_end=end,
        status=AppointmentStatus.BOOKED,
        origin=AppointmentOrigin.BOOKED,
        version=1,
    )
    db.add(appointment)
    try:
        db.flush()
    except IntegrityError:
        # The database overlap guard caught a race the checks above could not see.
        db.rollback()
        raise ConflictError("That time slot is no longer available") from None

    record_audit(
        db,
        entity_type="appointment",
        entity_id=appointment.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        after={
            "patient_id": data.patient_id,
            "doctor_id": data.doctor_id,
            "scheduled_start": start.isoformat(),
        },
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("That time slot is no longer available") from None
    db.refresh(appointment)
    return appointment


def cancel_appointment(
    db: Session,
    appointment_id: int,
    *,
    actor_id: int,
    reason: str | None = None,
    expected_version: int | None = None,
) -> Appointment:
    appt = db.get(Appointment, appointment_id, with_for_update={"of": Appointment})
    if appt is None:
        raise NotFoundError("Appointment not found")
    if appt.status in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED):
        raise ConflictError(f"Cannot cancel an appointment that is {appt.status.value}")
    if appt.status == AppointmentStatus.IN_PROGRESS:
        raise ConflictError("Cannot cancel a consultation that is in progress")
    if expected_version is not None and expected_version != appt.version:
        raise ConflictError("Appointment was modified by someone else; reload and retry")

    before = {"status": appt.status.value, "version": appt.version}
    appt.status = AppointmentStatus.CANCELLED
    appt.version += 1

    record_audit(
        db,
        entity_type="appointment",
        entity_id=appt.id,
        action=AuditAction.CANCEL,
        actor_id=actor_id,
        before=before,
        after={"status": appt.status.value, "version": appt.version},
        reason=reason,
    )
    db.commit()
    db.refresh(appt)
    return appt
