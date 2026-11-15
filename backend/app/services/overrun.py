"""Consultation overrun: a doctor's running-late consultation pushes later patients back.

``extend_consultation`` lengthens the in-progress appointment and ripples the doctor's later
bookings forward just enough to stay clear of it — a gap in the day absorbs the delay, so the
ripple stops at the first appointment that still fits. Everything moved is recorded as a
displacement under a ``consult_overrun`` decision (so it shows on the Displacements and Decisions
screens), audited, and each moved patient gets a notification. The change is all-or-nothing:
if any appointment cannot be moved safely, nothing changes and the doctor is told why.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AppointmentStatus, AuditAction, Role
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.appointment import Appointment
from app.models.base import ensure_aware_utc, utcnow
from app.models.decision import SchedulingDecision
from app.models.displacement import AppointmentDisplacement
from app.models.user import User
from app.scheduling.availability import Interval
from app.services.audit import record_audit
from app.services.locking import lock_doctors
from app.services.notifications import queue_moved
from app.services.scheduling import _patient_busy_intervals, _shift_intervals

TRIGGER = "consult_overrun"
ENGINE_VERSION = "overrun-1"
MAX_CONSULT = timedelta(hours=4)
_MOVABLE = (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN)


def plan_ripple(
    later: list[Appointment], new_end: datetime, shifts: list[Interval]
) -> list[tuple[Appointment, datetime]]:
    """Pure: which of ``later`` (sorted by start) must move, and to when.

    A moved appointment keeps its duration. If it would run past the end of its working block
    it jumps to the start of the next block (e.g. across lunch); if there is none, the plan is
    impossible and ``ConflictError`` explains which patient could not be fitted.
    """
    cursor = new_end
    moves: list[tuple[Appointment, datetime]] = []
    for appt in later:
        start = ensure_aware_utc(appt.scheduled_start)
        if start >= cursor:
            break  # this one (and everything after) is already clear of the overrun
        duration = ensure_aware_utc(appt.scheduled_end) - start
        new_start = cursor
        if not any(s.start <= new_start and new_start + duration <= s.end for s in shifts):
            following = sorted((s for s in shifts if s.start >= cursor), key=lambda s: s.start)
            if not following or following[0].start + duration > following[0].end:
                raise ConflictError(
                    f"Extending would push {appt.patient.name} past the end of the doctor's "
                    "working hours. Reschedule or cancel them first.",
                    details={"code": "overrun_exceeds_shift"},
                )
            new_start = following[0].start
        moves.append((appt, new_start))
        cursor = new_start + duration
    return moves


def extend_consultation(
    db: Session,
    appointment_id: int,
    minutes: int,
    *,
    actor: User,
    expected_version: int | None = None,
) -> dict[str, Any]:
    if actor.role not in (Role.DOCTOR, Role.ADMINISTRATOR):
        raise ForbiddenError("Only the doctor or an administrator can extend a consultation")
    peek = db.get(Appointment, appointment_id)
    if peek is None:
        raise NotFoundError("Appointment not found")
    if actor.role == Role.DOCTOR and peek.doctor_id != actor.id:
        raise ForbiddenError("You can only extend your own consultations")

    lock_doctors(db, [peek.doctor_id])  # same lock order as the emergency flow
    appt = db.get(
        Appointment, appointment_id, with_for_update={"of": Appointment}, populate_existing=True
    )
    assert appt is not None
    if appt.status != AppointmentStatus.IN_PROGRESS:
        raise ConflictError(
            f"Only a consultation in progress can be extended (this one is {appt.status.value})",
            details={"code": "invalid_transition"},
        )
    if expected_version is not None and expected_version != appt.version:
        raise ConflictError("Appointment was modified by someone else; reload and retry")

    now = utcnow()
    start = ensure_aware_utc(appt.scheduled_start)
    old_end = ensure_aware_utc(appt.scheduled_end)
    new_end = max(old_end, now) + timedelta(minutes=minutes)  # extend from "now" if already over
    if new_end - start > MAX_CONSULT:
        raise ValidationError("A consultation can't be extended beyond 4 hours in total")

    lo, hi = start - timedelta(hours=12), new_end + timedelta(hours=36)
    shifts = _shift_intervals(db, appt.doctor_id, lo, hi)
    later = list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.doctor_id == appt.doctor_id,
                Appointment.id != appt.id,
                Appointment.status.in_(_MOVABLE),
                Appointment.scheduled_start >= old_end - timedelta(minutes=1),
                Appointment.scheduled_start < hi,
            )
            .order_by(Appointment.scheduled_start)
            .with_for_update(of=Appointment)
        )
    )
    moves = plan_ripple(later, new_end, shifts)

    # Never move someone onto a time they are already booked elsewhere.
    for moved, new_start in moves:
        span = moved.scheduled_end - moved.scheduled_start
        window = Interval(new_start, new_start + span)
        for other in _patient_busy_intervals(db, moved.patient_id, lo, hi):
            clash = other.overlaps(window) and not (
                other.start == moved.scheduled_start and other.end == moved.scheduled_end
            )
            if clash:
                raise ConflictError(
                    f"{moved.patient.name} is already booked elsewhere at the new time. "
                    "Reschedule them manually first.",
                    details={"code": "patient_overlap"},
                )

    try:
        decision_id: int | None = None
        displaced: list[dict[str, Any]] = []
        if moves:
            decision = SchedulingDecision(
                trigger=TRIGGER,
                status="auto_committed",
                engine_version=ENGINE_VERSION,
                actor_id=actor.id,
                patient_id=appt.patient_id,
                input_snapshot={
                    "appointment_id": appt.id,
                    "minutes": minutes,
                    "old_end": old_end.isoformat(),
                    "new_end": new_end.isoformat(),
                },
                chosen_plan=None,
                alternatives=[],
                parameters={"minutes": minutes, "max_consult_min": MAX_CONSULT.seconds // 60},
                reasons=["consultation_overrun"],
            )
            db.add(decision)
            db.flush()
            decision_id = decision.id
        # Last-to-first, one flush each: every appointment lands in space that is already free,
        # so the database overlap guard never sees a transient clash. The doctor's own
        # appointment is extended last, into the space the moves vacated.
        for moved, new_start in reversed(moves):
            from_start = ensure_aware_utc(moved.scheduled_start)
            span = ensure_aware_utc(moved.scheduled_end) - from_start
            moved.scheduled_start = new_start
            moved.scheduled_end = new_start + span
            moved.version += 1
            db.flush()
            assert decision_id is not None
            db.add(
                AppointmentDisplacement(
                    appointment_id=moved.id,
                    decision_id=decision_id,
                    from_start=from_start,
                    to_start=new_start,
                    reason="consultation_overrun",
                )
            )
            record_audit(
                db,
                entity_type="appointment",
                entity_id=moved.id,
                action=AuditAction.UPDATE,
                actor_id=actor.id,
                before={"scheduled_start": from_start.isoformat()},
                after={"scheduled_start": new_start.isoformat()},
                reason="displaced_by_consultation_overrun",
            )
            queue_moved(
                db, moved, from_start=from_start, to_start=new_start,
                decision_id=decision_id, reason="overrun",
            )
            displaced.append(
                {
                    "appointment_id": moved.id,
                    "patient_name": moved.patient.name,
                    "from_start": from_start.isoformat(),
                    "to_start": new_start.isoformat(),
                }
            )
        displaced.reverse()

        appt.scheduled_end = new_end
        appt.version += 1
        record_audit(
            db,
            entity_type="appointment",
            entity_id=appt.id,
            action=AuditAction.UPDATE,
            actor_id=actor.id,
            before={"scheduled_end": old_end.isoformat()},
            after={"scheduled_end": new_end.isoformat()},
            reason=f"consultation_extended_{minutes}min",
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            "The schedule changed while extending; please retry.",
            details={"code": "schedule_changed"},
        ) from None
    db.refresh(appt)
    return {
        "id": appt.id,
        "scheduled_end": appt.scheduled_end,
        "version": appt.version,
        "decision_id": decision_id,
        "displaced": displaced,
    }
