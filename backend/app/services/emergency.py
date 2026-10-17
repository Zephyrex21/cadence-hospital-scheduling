"""Emergency scheduling service: triage, dry-run planning, and transactional commit.

The plan/commit split is both a UX and a safety mechanism:

* ``plan_emergency`` runs the pure engine against a snapshot and returns the
  proposed plan (and alternatives) **without touching the schedule**.
* ``commit_emergency`` re-fetches the schedule under a row lock, verifies it has
  not changed since the plan was reviewed (fingerprint), re-runs the engine, and
  applies the result atomically — but only when the engine auto-approves. A1 /
  escalated plans are never auto-applied; they are recorded and surfaced for a
  human. An idempotency key makes a double-clicked commit a no-op.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Acuity, AppointmentOrigin, AppointmentStatus, AuditAction
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.base import ensure_aware_utc, utcnow
from app.models.decision import SchedulingDecision
from app.models.displacement import AppointmentDisplacement
from app.models.patient import Patient
from app.models.triage import TriageAssessment
from app.models.user import User
from app.scheduling.engine import EngineRequest, insert_emergency
from app.scheduling.engine_adapter import (
    active_appointments,
    build_engine_state,
    eligible_doctor_ids,
    serialize_decision,
    state_fingerprint,
)
from app.services.audit import record_audit

_TRIGGER = "emergency_insert"

# A triage assessment must be no older than this to authorize scheduling.
TRIAGE_VALIDITY = timedelta(hours=12)
# A reviewed plan older than this (wall-clock) is rejected at commit — re-plan.
PLAN_MAX_AGE = timedelta(minutes=10)


def create_triage(
    db: Session,
    *,
    patient_id: int,
    nurse_id: int,
    acuity: Acuity,
    chief_complaint: str,
    vitals: dict[str, Any] | None,
) -> TriageAssessment:
    if db.get(Patient, patient_id) is None:
        raise NotFoundError("Patient not found")
    assessment = TriageAssessment(
        patient_id=patient_id,
        nurse_id=nurse_id,
        acuity=acuity,
        chief_complaint=chief_complaint,
        vitals=vitals,
    )
    db.add(assessment)
    db.flush()
    record_audit(
        db,
        entity_type="triage",
        entity_id=assessment.id,
        action=AuditAction.CREATE,
        actor_id=nurse_id,
        after={"patient_id": patient_id, "acuity": acuity.value},
    )
    db.commit()
    db.refresh(assessment)
    return assessment


def _resolve(db: Session, patient_id: int, type_id: int) -> tuple[Patient, AppointmentType]:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise NotFoundError("Patient not found")
    appt_type = db.get(AppointmentType, type_id)
    if appt_type is None:
        raise NotFoundError("Appointment type not found")
    return patient, appt_type


def latest_triage(
    db: Session, patient_id: int, *, now: datetime | None = None
) -> TriageAssessment | None:
    """The patient's most recent triage, but only if still within the validity
    window. Older or absent → None (a nurse must triage before scheduling)."""
    at = ensure_aware_utc(now) if now is not None else utcnow()
    row = db.scalar(
        select(TriageAssessment)
        .where(TriageAssessment.patient_id == patient_id)
        .order_by(TriageAssessment.assessed_at.desc())
        .limit(1)
    )
    if row is None:
        return None
    if ensure_aware_utc(row.assessed_at) < at - TRIAGE_VALIDITY:
        return None
    return row


def _require_matching_triage(
    db: Session, patient_id: int, acuity: Acuity, at: datetime
) -> TriageAssessment:
    """Acuity is a nurse's clinical judgment — the server refuses to plan or
    commit unless a recent triage exists and the requested acuity matches it."""
    row = latest_triage(db, patient_id, now=at)
    if row is None:
        raise ValidationError(
            "A nurse must triage this patient before scheduling.",
            details={"code": "triage_required"},
        )
    if row.acuity != acuity:
        raise ValidationError(
            "Requested acuity does not match the nurse's recorded assessment; "
            "re-check the triage.",
            details={
                "code": "acuity_mismatch",
                "recorded_acuity": row.acuity.value,
                "requested_acuity": acuity.value,
            },
        )
    return row


def _appointment_details(db: Session, appointment_ids: set[int]) -> dict[str, dict[str, Any]]:
    if not appointment_ids:
        return {}
    rows = db.scalars(select(Appointment).where(Appointment.id.in_(appointment_ids)))
    details: dict[str, dict[str, Any]] = {}
    for a in rows:
        details[str(a.id)] = {
            "patient_name": a.patient.name,
            "mrn": a.patient.mrn,
            "type_name": a.type.name,
            "doctor_name": a.doctor.name,
            "acuity": a.acuity.value,
        }
    return details


def _enrich(db: Session, decision_dict: dict[str, Any], doctor_ids: list[int]) -> dict[str, Any]:
    appt_ids: set[int] = set()
    plans = list(decision_dict["alternatives"])
    if decision_dict["chosen"]:
        plans.append(decision_dict["chosen"])
    for plan in plans:
        for move in plan["moves"]:
            appt_ids.add(move["appointment_id"])

    doctor_rows = (
        list(db.scalars(select(User).where(User.id.in_(doctor_ids)))) if doctor_ids else []
    )
    return {
        "appointment_details": _appointment_details(db, appt_ids),
        "doctor_names": {str(u.id): u.name for u in doctor_rows},
    }


def plan_emergency(
    db: Session,
    *,
    patient_id: int,
    type_id: int,
    acuity: Acuity,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Dry-run: compute the proposed plan without mutating the schedule."""
    patient, appt_type = _resolve(db, patient_id, type_id)
    at = ensure_aware_utc(now) if now is not None else utcnow()
    _require_matching_triage(db, patient_id, acuity, at)

    doctor_ids = eligible_doctor_ids(db, appt_type.specialty, at)
    appts = active_appointments(db, doctor_ids, at)
    state = build_engine_state(db, doctor_ids, at, appts, emergency_patient_id=patient_id)
    request = EngineRequest(
        patient_id=patient_id,
        acuity=acuity,
        duration_min=appt_type.default_duration_min,
        eligible_doctor_ids=tuple(doctor_ids),
        now=at,
    )
    decision = insert_emergency(state, request)
    decision_dict = serialize_decision(decision)

    return {
        "fingerprint": state_fingerprint(appts),
        "now": at.isoformat(),
        "decision": decision_dict,
        "emergency_patient": {"id": patient.id, "name": patient.name, "mrn": patient.mrn},
        **_enrich(db, decision_dict, doctor_ids),
    }


def commit_emergency(
    db: Session,
    *,
    actor_id: int,
    patient_id: int,
    type_id: int,
    acuity: Acuity,
    fingerprint: str,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply the plan atomically — but only when the engine auto-approves."""
    # Idempotency: a repeated commit with the same key returns the first result.
    if idempotency_key:
        prior = db.scalar(
            select(SchedulingDecision).where(
                SchedulingDecision.idempotency_key == idempotency_key
            )
        )
        if prior is not None:
            return _commit_result(db, prior)

    patient, appt_type = _resolve(db, patient_id, type_id)
    at = ensure_aware_utc(now) if now is not None else utcnow()
    _require_matching_triage(db, patient_id, acuity, at)

    # A reviewed plan carries the "now" it was computed against; reject a commit
    # whose plan has gone stale on the wall clock so the engine never applies a
    # placement reasoned against an out-of-date picture of the day.
    if utcnow() - at > PLAN_MAX_AGE:
        raise ConflictError(
            "This plan has expired; please re-plan before committing.",
            details={"code": "plan_expired"},
        )

    doctor_ids = eligible_doctor_ids(db, appt_type.specialty, at)
    # Row-lock the active schedule so no concurrent change slips past the re-check.
    appts = active_appointments(db, doctor_ids, at, for_update=True)
    if state_fingerprint(appts) != fingerprint:
        raise ConflictError(
            "The schedule changed since this plan was reviewed; please re-plan.",
            details={"code": "schedule_changed"},
        )

    state = build_engine_state(db, doctor_ids, at, appts, emergency_patient_id=patient_id)
    request = EngineRequest(
        patient_id=patient_id,
        acuity=acuity,
        duration_min=appt_type.default_duration_min,
        eligible_doctor_ids=tuple(doctor_ids),
        now=at,
    )
    decision = insert_emergency(state, request)
    decision_dict = serialize_decision(decision)
    snapshot: dict[str, Any] = {
        "fingerprint": fingerprint,
        "appointments": [
            {
                "id": a.id,
                "doctor_id": a.doctor_id,
                "start": a.scheduled_start.isoformat(),
                "end": a.scheduled_end.isoformat(),
                "status": a.status.value,
                "acuity": a.acuity.value,
                "displacement_count": a.displacement_count,
            }
            for a in appts
        ],
    }

    if decision.status != "auto" or decision.chosen is None:
        # Record the escalation for the audit trail; do not mutate the schedule.
        record = SchedulingDecision(
            trigger=_TRIGGER,
            status="escalated",
            engine_version=decision.engine_version,
            actor_id=actor_id,
            patient_id=patient_id,
            emergency_appointment_id=None,
            idempotency_key=idempotency_key,
            input_snapshot=snapshot,
            chosen_plan=decision_dict["chosen"],
            alternatives=decision_dict["alternatives"],
            parameters=decision_dict["parameters"],
            reasons=list(decision.reasons),
        )
        db.add(record)
        db.flush()
        db.commit()
        return _commit_result(db, record)

    chosen = decision.chosen
    by_id = {a.id: a for a in appts}

    emergency = Appointment(
        patient_id=patient_id,
        doctor_id=chosen.placement.doctor_id,
        type_id=type_id,
        scheduled_start=chosen.placement.start,
        scheduled_end=chosen.placement.end,
        status=AppointmentStatus.BOOKED,
        origin=AppointmentOrigin.EMERGENCY,
        acuity=acuity,
        displacement_count=0,
        version=1,
    )
    db.add(emergency)
    db.flush()

    record = SchedulingDecision(
        trigger=_TRIGGER,
        status="auto_committed",
        engine_version=decision.engine_version,
        actor_id=actor_id,
        patient_id=patient_id,
        emergency_appointment_id=emergency.id,
        idempotency_key=idempotency_key,
        input_snapshot=snapshot,
        chosen_plan=decision_dict["chosen"],
        alternatives=decision_dict["alternatives"],
        parameters=decision_dict["parameters"],
        reasons=[],
    )
    db.add(record)
    db.flush()

    for move in chosen.moves:
        appt = by_id[move.appointment_id]
        assert move.to_start is not None  # feasible plans never drop an appointment
        from_start = appt.scheduled_start
        appt_duration = appt.scheduled_end - appt.scheduled_start
        before = {
            "scheduled_start": from_start.isoformat(),
            "displacement_count": appt.displacement_count,
        }
        appt.scheduled_start = move.to_start
        appt.scheduled_end = move.to_start + appt_duration
        appt.displacement_count += 1
        appt.version += 1
        db.add(
            AppointmentDisplacement(
                appointment_id=appt.id,
                decision_id=record.id,
                from_start=from_start,
                to_start=move.to_start,
                reason=move.reason,
            )
        )
        record_audit(
            db,
            entity_type="appointment",
            entity_id=appt.id,
            action=AuditAction.UPDATE,
            actor_id=actor_id,
            before=before,
            after={
                "scheduled_start": appt.scheduled_start.isoformat(),
                "displacement_count": appt.displacement_count,
            },
            reason="displaced_by_emergency",
        )

    record_audit(
        db,
        entity_type="appointment",
        entity_id=emergency.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        after={"origin": "emergency", "acuity": acuity.value},
        reason="emergency_insertion",
    )
    db.commit()
    return _commit_result(db, record)


def _commit_result(db: Session, record: SchedulingDecision) -> dict[str, Any]:
    displaced = db.scalars(
        select(AppointmentDisplacement).where(
            AppointmentDisplacement.decision_id == record.id
        )
    )
    details: list[dict[str, Any]] = []
    for d in displaced:
        appt = db.get(Appointment, d.appointment_id)
        details.append(
            {
                "appointment_id": d.appointment_id,
                "patient_name": appt.patient.name if appt else "",
                "from_start": d.from_start.isoformat(),
                "to_start": d.to_start.isoformat(),
            }
        )
    status = "auto" if record.status == "auto_committed" else "escalate"
    return {
        "status": status,
        "decision_id": record.id,
        "emergency_appointment_id": record.emergency_appointment_id,
        "reasons": list(record.reasons),
        "displaced": details,
    }
