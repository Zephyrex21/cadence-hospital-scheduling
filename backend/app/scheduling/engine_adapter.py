"""Adapter between the database and the pure scheduling engine.

Fetches a day's shifts and active appointments, maps them into the engine's
immutable ``EngineState``, and serializes the resulting ``Decision`` to a
JSON-safe structure for the API response and the persisted decision record.
Keeping this seam thin means the engine stays pure and independently testable.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AppointmentStatus
from app.models.appointment import Appointment
from app.models.doctor import DoctorProfile
from app.models.shift import Shift
from app.models.user import User
from app.scheduling.availability import Interval
from app.scheduling.engine import (
    CandidatePlan,
    Decision,
    EngineAppointment,
    EngineParameters,
    EngineState,
    Move,
)

# Statuses that occupy a doctor's time (mirrors the booking service).
_ACTIVE = (
    AppointmentStatus.BOOKED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.IN_PROGRESS,
)


# The engine plans over a rolling horizon around "now" rather than a UTC calendar
# day: a clinic day (and a night shift) routinely straddles UTC midnight, and an
# appointment just after midnight must still be visible to a placement just before.
_HORIZON_BEFORE = timedelta(hours=12)
_HORIZON_AFTER = timedelta(hours=36)


def _horizon(now: datetime) -> tuple[datetime, datetime]:
    return now - _HORIZON_BEFORE, now + _HORIZON_AFTER


def eligible_doctor_ids(db: Session, specialty: str, now: datetime) -> list[int]:
    """Doctors of the given specialty with a shift within the planning horizon."""
    lo, hi = _horizon(now)
    rows = db.execute(
        select(User.id)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .join(Shift, Shift.doctor_id == User.id)
        .where(
            DoctorProfile.specialty == specialty,
            Shift.start_utc < hi,
            Shift.end_utc > lo,
        )
        .distinct()
        .order_by(User.id)
    ).all()
    return [r[0] for r in rows]


def active_appointments(
    db: Session, doctor_ids: list[int], now: datetime, *, for_update: bool = False
) -> list[Appointment]:
    lo, hi = _horizon(now)
    if not doctor_ids:
        return []
    stmt = select(Appointment).where(
        Appointment.doctor_id.in_(doctor_ids),
        Appointment.status.in_(_ACTIVE),
        Appointment.scheduled_start < hi,
        Appointment.scheduled_end > lo,
    )
    if for_update:
        stmt = stmt.with_for_update(of=Appointment)
    return list(db.scalars(stmt.order_by(Appointment.doctor_id, Appointment.scheduled_start)))


def build_engine_state(
    db: Session,
    doctor_ids: list[int],
    now: datetime,
    appointments: list[Appointment],
    *,
    emergency_patient_id: int | None = None,
) -> EngineState:
    lo, hi = _horizon(now)
    shifts: dict[int, tuple[Interval, ...]] = {}
    for doctor_id in doctor_ids:
        rows = db.scalars(
            select(Shift).where(
                Shift.doctor_id == doctor_id, Shift.start_utc < hi, Shift.end_utc > lo
            )
        )
        shifts[doctor_id] = tuple(Interval(s.start_utc, s.end_utc) for s in rows)

    engine_appts = tuple(
        EngineAppointment(
            id=a.id,
            doctor_id=a.doctor_id,
            patient_id=a.patient_id,
            start=a.scheduled_start,
            end=a.scheduled_end,
            status=a.status,
            acuity=a.acuity,
            displacement_count=a.displacement_count,
        )
        for a in appointments
    )
    return EngineState(
        shifts=shifts,
        appointments=engine_appts,
        patient_busy=_patient_busy(db, doctor_ids, lo, hi, appointments, emergency_patient_id),
    )


def _patient_busy(
    db: Session,
    doctor_ids: list[int],
    lo: datetime,
    hi: datetime,
    appointments: list[Appointment],
    emergency_patient_id: int | None,
) -> dict[int, tuple[Interval, ...]]:
    """Each relevant patient's active appointments on doctors *outside* the
    eligible set, so the engine won't place or ripple into a time they are
    already booked elsewhere. Appointments on eligible doctors are already in the
    engine state and handled by the cascade, so they are excluded here."""
    if not doctor_ids:
        return {}
    patient_ids = {a.patient_id for a in appointments}
    if emergency_patient_id is not None:
        patient_ids.add(emergency_patient_id)
    if not patient_ids:
        return {}

    rows = db.scalars(
        select(Appointment).where(
            Appointment.patient_id.in_(patient_ids),
            Appointment.doctor_id.notin_(doctor_ids),
            Appointment.status.in_(_ACTIVE),
            Appointment.scheduled_start < hi,
            Appointment.scheduled_end > lo,
        )
    )
    busy: dict[int, list[Interval]] = {}
    for a in rows:
        busy.setdefault(a.patient_id, []).append(Interval(a.scheduled_start, a.scheduled_end))
    return {pid: tuple(ivs) for pid, ivs in busy.items()}


def state_fingerprint(appointments: list[Appointment]) -> str:
    """Stable hash of the active schedule the plan was computed against.

    If the schedule changes between plan and commit, the fingerprint changes and
    commit rejects the stale plan ("schedule changed, re-plan").
    """
    canonical = "|".join(
        f"{a.id}:{a.scheduled_start.isoformat()}:{a.scheduled_end.isoformat()}:"
        f"{a.status.value}:{a.version}:{a.displacement_count}"
        for a in sorted(appointments, key=lambda a: a.id)
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def plan_digest(plan: dict[str, Any] | None) -> str | None:
    """Stable hash of what a reviewer actually approved: the placement and moves.

    Commit recomputes the plan on the server's clock; if it no longer matches the
    digest the reviewer saw, the commit is refused and the user re-plans.
    """
    if plan is None:
        return None
    placement = plan["placement"]
    moves = sorted(plan["moves"], key=lambda m: m["appointment_id"])
    canonical = f"{placement['doctor_id']}|{placement['start']}|{placement['end']}|" + "|".join(
        f"{m['appointment_id']}:{m['to_start']}" for m in moves
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def request_hash(actor_id: int, patient_id: int, type_id: int, acuity: str) -> str:
    return hashlib.sha256(f"{actor_id}|{patient_id}|{type_id}|{acuity}".encode()).hexdigest()


def _delay_min(move: Move) -> float | None:
    if move.to_start is None:
        return None
    return (move.to_start - move.from_start).total_seconds() / 60.0


def _serialize_plan(plan: CandidatePlan) -> dict[str, Any]:
    return {
        "placement": {
            "doctor_id": plan.placement.doctor_id,
            "start": plan.placement.start.isoformat(),
            "end": plan.placement.end.isoformat(),
        },
        "cost": plan.cost,
        "feasible": plan.feasible,
        "reject_reasons": list(plan.reject_reasons),
        "moves": [
            {
                "appointment_id": m.appointment_id,
                "doctor_id": m.doctor_id,
                "from_start": m.from_start.isoformat(),
                "to_start": m.to_start.isoformat() if m.to_start else None,
                "delay_min": _delay_min(m),
                "duration_min": m.duration_min,
                "reason": m.reason,
            }
            for m in plan.moves
        ],
    }


def _serialize_parameters(params: EngineParameters) -> dict[str, Any]:
    return {
        "response_window_min": {a.value: m for a, m in params.response_window_min.items()},
        "max_displacements": params.max_displacements,
        "max_auto_delay_min": params.max_auto_delay_min,
        "max_auto_displaced": params.max_auto_displaced,
        "slot_step_min": params.slot_step_min,
        "escalation_cost_threshold": params.escalation_cost_threshold,
        "w_delay": params.w_delay,
        "w_count": params.w_count,
        "w_continuity": params.w_continuity,
        "w_fairness_base": params.w_fairness_base,
    }


def serialize_decision(decision: Decision) -> dict[str, Any]:
    """JSON-safe view of a Decision for the API response and the audit record."""
    req = decision.request
    return {
        "status": decision.status,
        "engine_version": decision.engine_version,
        "reasons": list(decision.reasons),
        "request": {
            "patient_id": req.patient_id,
            "acuity": req.acuity.value,
            "duration_min": req.duration_min,
            "now": req.now.isoformat(),
            "eligible_doctor_ids": list(req.eligible_doctor_ids),
        },
        "parameters": _serialize_parameters(decision.parameters),
        "chosen": _serialize_plan(decision.chosen) if decision.chosen else None,
        "alternatives": [_serialize_plan(p) for p in decision.alternatives],
    }
