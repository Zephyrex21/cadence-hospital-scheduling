"""Read-side history service: displacements, decision traces, and the audit log.

All data here is already persisted by the booking/emergency/consultation flows;
this module only reads and enriches it (joining in patient/doctor/actor names) so
staff can see what moved and administrators can see exactly why.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import clinic_day_bounds
from app.core.enums import AuditAction
from app.core.errors import ConflictError, NotFoundError
from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.base import utcnow
from app.models.decision import SchedulingDecision
from app.models.displacement import AppointmentDisplacement
from app.models.patient import Patient
from app.models.user import User
from app.services.audit import record_audit

_MAX_ROWS = 200


def _delay_min(from_start: datetime, to_start: datetime) -> int:
    return round((to_start - from_start).total_seconds() / 60.0)


def _user_names(db: Session, ids: set[int]) -> dict[int, str]:
    clean = {i for i in ids if i}
    if not clean:
        return {}
    rows = db.scalars(select(User).where(User.id.in_(clean)))
    return {u.id: u.name for u in rows}


def list_displacements(db: Session, day: datetime | None = None) -> list[dict[str, Any]]:
    stmt = select(AppointmentDisplacement)
    if day is not None:
        lo, hi = clinic_day_bounds(day)
        stmt = stmt.where(
            AppointmentDisplacement.created_at >= lo, AppointmentDisplacement.created_at < hi
        )
    rows = list(
        db.scalars(stmt.order_by(AppointmentDisplacement.created_at.desc()).limit(_MAX_ROWS))
    )

    result: list[dict[str, Any]] = []
    for d in rows:
        appt = db.get(Appointment, d.appointment_id)
        result.append(
            {
                "id": d.id,
                "appointment_id": d.appointment_id,
                "decision_id": d.decision_id,
                "patient_name": appt.patient.name if appt else "",
                "mrn": appt.patient.mrn if appt else "",
                "doctor_name": appt.doctor.name if appt else "",
                "from_start": d.from_start.isoformat(),
                "to_start": d.to_start.isoformat(),
                "delay_min": _delay_min(d.from_start, d.to_start),
                "reason": d.reason,
                "created_at": d.created_at.isoformat(),
            }
        )
    return result


def list_decisions(db: Session, day: datetime | None = None) -> list[dict[str, Any]]:
    stmt = select(SchedulingDecision)
    if day is not None:
        lo, hi = clinic_day_bounds(day)
        stmt = stmt.where(
            SchedulingDecision.created_at >= lo, SchedulingDecision.created_at < hi
        )
    rows = list(db.scalars(stmt.order_by(SchedulingDecision.created_at.desc()).limit(_MAX_ROWS)))

    actor_names = _user_names(db, {r.actor_id for r in rows})
    patient_ids = {r.patient_id for r in rows}
    patients: dict[int, str] = {}
    if patient_ids:
        patients = {
            p.id: p.name
            for p in db.scalars(select(Patient).where(Patient.id.in_(patient_ids)))
        }

    displaced_counts = _displaced_counts(db, {r.id for r in rows})

    result: list[dict[str, Any]] = []
    for r in rows:
        result.append(
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "trigger": r.trigger,
                "status": r.status,
                "engine_version": r.engine_version,
                "patient_name": patients.get(r.patient_id, ""),
                "actor_name": actor_names.get(r.actor_id, ""),
                "emergency_appointment_id": r.emergency_appointment_id,
                "reason_count": len(r.reasons or []),
                "displaced_count": displaced_counts.get(r.id, 0),
            }
        )
    return result


def _displaced_counts(db: Session, decision_ids: set[int]) -> dict[int, int]:
    if not decision_ids:
        return {}
    rows = db.scalars(
        select(AppointmentDisplacement).where(
            AppointmentDisplacement.decision_id.in_(decision_ids)
        )
    )
    counts: dict[int, int] = {}
    for d in rows:
        counts[d.decision_id] = counts.get(d.decision_id, 0) + 1
    return counts


def get_decision(db: Session, decision_id: int) -> dict[str, Any] | None:
    record = db.get(SchedulingDecision, decision_id)
    if record is None:
        return None

    actor = db.get(User, record.actor_id)
    patient = db.get(Patient, record.patient_id)

    displacements = db.scalars(
        select(AppointmentDisplacement)
        .where(AppointmentDisplacement.decision_id == decision_id)
        .order_by(AppointmentDisplacement.id)
    )
    displaced: list[dict[str, Any]] = []
    for d in displacements:
        appt = db.get(Appointment, d.appointment_id)
        displaced.append(
            {
                "appointment_id": d.appointment_id,
                "patient_name": appt.patient.name if appt else "",
                "from_start": d.from_start.isoformat(),
                "to_start": d.to_start.isoformat(),
                "delay_min": _delay_min(d.from_start, d.to_start),
                "reason": d.reason,
            }
        )

    return {
        "id": record.id,
        "trigger": record.trigger,
        "status": record.status,
        "engine_version": record.engine_version,
        "created_at": record.created_at.isoformat(),
        "actor": {"id": record.actor_id, "name": actor.name if actor else ""},
        "patient": {
            "id": record.patient_id,
            "name": patient.name if patient else "",
            "mrn": patient.mrn if patient else "",
        },
        "emergency_appointment_id": record.emergency_appointment_id,
        "reasons": list(record.reasons or []),
        "chosen_plan": record.chosen_plan,
        "alternatives": list(record.alternatives or []),
        "parameters": record.parameters,
        "input_snapshot": record.input_snapshot,
        "displacements": displaced,
    }


def resolve_decision(
    db: Session, decision_id: int, *, actor_id: int, note: str
) -> dict[str, Any]:
    """Mark an escalated decision resolved (how a human handled it), with a note.

    Append-only: the original decision is never altered beyond the resolution
    fields, and the resolution is recorded in the audit log.
    """
    record = db.get(SchedulingDecision, decision_id, with_for_update=True)
    if record is None:
        raise NotFoundError("Decision not found")
    if record.status != "escalated":
        raise ConflictError(
            "Only escalated decisions can be resolved.",
            details={"code": "not_escalated"},
        )
    if record.resolved_at is not None:
        raise ConflictError(
            "This escalation has already been resolved.",
            details={"code": "already_resolved"},
        )

    record.resolved_at = utcnow()
    record.resolved_by = actor_id
    record.resolution_note = note
    record_audit(
        db,
        entity_type="scheduling_decision",
        entity_id=record.id,
        action=AuditAction.RESOLVE,
        actor_id=actor_id,
        after={"resolved_at": record.resolved_at.isoformat()},
        reason=note,
    )
    db.commit()
    db.refresh(record)
    resolver = db.get(User, actor_id)
    return {
        "id": record.id,
        "resolved_at": record.resolved_at.isoformat(),
        "resolved_by": {"id": actor_id, "name": resolver.name if resolver else ""},
        "resolution_note": record.resolution_note,
    }


def list_audit(
    db: Session, entity_type: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    stmt = select(AuditLog)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    rows = list(db.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(min(limit, _MAX_ROWS))))

    actor_names = _user_names(db, {r.actor_id for r in rows if r.actor_id is not None})
    return [
        {
            "id": r.id,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "action": r.action,
            "actor_name": actor_names.get(r.actor_id, "") if r.actor_id else "system",
            "reason": r.reason,
            "before": r.before,
            "after": r.after,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
