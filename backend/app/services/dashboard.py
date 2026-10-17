"""Dashboard service: live operational workload summary.

Aggregates today's schedule into the tiles the operations lead watches — waiting
counts by acuity, in-progress consultations, displacements, pending escalations,
and a per-doctor load table with running delay.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Acuity, AppointmentStatus
from app.models.appointment import Appointment
from app.models.base import ensure_aware_utc
from app.models.decision import SchedulingDecision
from app.models.displacement import AppointmentDisplacement
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.user import User
from app.scheduling.dashboard import doctor_running_delay
from app.scheduling.queue import QueueItem

_ACTIVE = (
    AppointmentStatus.BOOKED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.IN_PROGRESS,
)
_WAITING = (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN)
_MAX_ESCALATIONS = 10


def _day_bounds(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def _count(db: Session, stmt: Any) -> int:
    return len(list(db.scalars(stmt)))


def summary(db: Session, now: datetime) -> dict[str, Any]:
    now = ensure_aware_utc(now)
    lo, hi = _day_bounds(now)

    active = list(
        db.scalars(
            select(Appointment).where(
                Appointment.status.in_(_ACTIVE),
                Appointment.scheduled_start < hi,
                Appointment.scheduled_end > lo,
            )
        )
    )

    waiting_by_acuity: dict[str, int] = {a.value: 0 for a in Acuity}
    total_waiting = 0
    in_progress = 0
    for a in active:
        if a.status in _WAITING:
            waiting_by_acuity[a.acuity.value] += 1
            total_waiting += 1
        elif a.status == AppointmentStatus.IN_PROGRESS:
            in_progress += 1

    completed_today = _count(
        db,
        select(Appointment).where(
            Appointment.status == AppointmentStatus.COMPLETED,
            Appointment.scheduled_start < hi,
            Appointment.scheduled_end > lo,
        ),
    )
    displaced_today = _count(
        db,
        select(AppointmentDisplacement).where(
            AppointmentDisplacement.created_at >= lo,
            AppointmentDisplacement.created_at < hi,
        ),
    )

    escalations = list(
        db.scalars(
            select(SchedulingDecision)
            .where(
                SchedulingDecision.status == "escalated",
                SchedulingDecision.resolved_at.is_(None),
            )
            .order_by(SchedulingDecision.created_at.desc())
            .limit(_MAX_ESCALATIONS)
        )
    )
    # The true pending count spans every day and is not capped by the list limit.
    escalations_pending = _count(
        db,
        select(SchedulingDecision).where(
            SchedulingDecision.status == "escalated",
            SchedulingDecision.resolved_at.is_(None),
        ),
    )
    esc_patient_names = _patient_names(db, {e.patient_id for e in escalations})
    recent_escalations = [
        {
            "decision_id": e.id,
            "patient_name": esc_patient_names.get(e.patient_id, ""),
            "created_at": e.created_at.isoformat(),
            "reasons": list(e.reasons or []),
        }
        for e in escalations
    ]

    doctor_load = _doctor_load(db, active, now)

    return {
        "now": now.isoformat(),
        "total_waiting": total_waiting,
        "in_progress": in_progress,
        "completed_today": completed_today,
        "displaced_today": displaced_today,
        "escalations_pending": escalations_pending,
        "waiting_by_acuity": waiting_by_acuity,
        "recent_escalations": recent_escalations,
        "doctor_load": doctor_load,
    }


def _patient_names(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {p.id: p.name for p in db.scalars(select(Patient).where(Patient.id.in_(ids)))}


def _doctor_load(
    db: Session, active: list[Appointment], now: datetime
) -> list[dict[str, Any]]:
    lo, hi = _day_bounds(now)
    on_shift = db.execute(
        select(User.id, User.name)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .join(Shift, Shift.doctor_id == User.id)
        .where(Shift.start_utc < hi, Shift.end_utc > lo)
        .distinct()
    ).all()

    by_doctor: dict[int, list[Appointment]] = {}
    for a in active:
        by_doctor.setdefault(a.doctor_id, []).append(a)

    load: list[dict[str, Any]] = []
    for doctor_id, name in on_shift:
        appts = by_doctor.get(doctor_id, [])
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
        load.append(
            {
                "doctor_id": doctor_id,
                "name": name,
                "waiting": sum(1 for a in appts if a.status in _WAITING),
                "in_progress": sum(1 for a in appts if a.status == AppointmentStatus.IN_PROGRESS),
                "running_delay_min": doctor_running_delay(items, now),
            }
        )

    load.sort(key=lambda d: (-d["running_delay_min"], d["name"]))
    return load
