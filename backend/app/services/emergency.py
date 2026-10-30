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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import resolve_now
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
from app.scheduling.engine import EngineRequest, insert_emergency, plan_at
from app.scheduling.engine_adapter import (
    active_appointments,
    build_engine_state,
    eligible_doctor_ids,
    plan_digest,
    request_hash,
    serialize_decision,
    state_fingerprint,
)
from app.services.audit import record_audit
from app.services.locking import lock_doctors

_TRIGGER = "emergency_insert"

# A triage assessment must be no older than this to authorize scheduling.
TRIAGE_VALIDITY = timedelta(hours=12)
# A reviewed plan older than this (wall-clock) is rejected at commit — re-plan.
# (Only meaningful when a client clock is allowed; otherwise the server clock is
# used on both plan and commit and the plan digest guards staleness.)
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
    at = resolve_now(now)
    row = db.scalar(
        select(TriageAssessment)
        .where(TriageAssessment.patient_id == patient_id)
        .order_by(TriageAssessment.assessed_at.desc())
        .limit(1)
    )
    if row is None:
        return None
    # One assessment authorises exactly one scheduled emergency: once consumed,
    # a new walk-in episode needs a fresh nurse assessment.
    if row.consumed_at is not None:
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
    at = resolve_now(now)
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
        "plan_digest": plan_digest(decision_dict["chosen"]),
        "now": at.isoformat(),
        "decision": decision_dict,
        "emergency_patient": {"id": patient.id, "name": patient.name, "mrn": patient.mrn},
        **_enrich(db, decision_dict, doctor_ids),
    }


def _replay(db: Session, key: str | None, rhash: str) -> dict[str, Any] | None:
    """Return the stored result for a repeated idempotency key.

    The key is bound to the request that created it: reusing it for a different
    patient/type/acuity/actor is an error, never someone else's result.
    """
    if not key:
        return None
    prior = db.scalar(
        select(SchedulingDecision).where(SchedulingDecision.idempotency_key == key)
    )
    if prior is None:
        return None
    if prior.request_hash is not None and prior.request_hash != rhash:
        raise ConflictError(
            "This idempotency key was already used for a different request.",
            details={"code": "idempotency_key_reused"},
        )
    return _commit_result(db, prior)


def _snapshot(
    fingerprint: str, appts: list[Appointment], *, type_id: int, acuity: Acuity
) -> dict[str, Any]:
    return {
        "fingerprint": fingerprint,
        # What an escalation needs in order to be applied later by a human.
        "request": {"type_id": type_id, "acuity": acuity.value},
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


def _apply_plan(
    db: Session,
    *,
    record: SchedulingDecision,
    actor_id: int,
    patient_id: int,
    type_id: int,
    acuity: Acuity,
    doctor_id: int,
    start: datetime,
    end: datetime,
    moves: list[tuple[int, datetime, str]],
    by_id: dict[int, Appointment],
) -> Appointment:
    """Write a validated plan. ``record`` is already flushed (has an id).

    Moves are applied **last-to-first, one flush each**: every rippled
    appointment lands in space that is already free, so no intermediate statement
    ever overlaps (the database overlap guards check each statement immediately).
    The emergency is inserted last, into the space the moves vacated.
    """
    for appt_id, to_start, reason in reversed(moves):
        appt = by_id[appt_id]
        from_start = appt.scheduled_start
        duration = appt.scheduled_end - appt.scheduled_start
        before = {
            "scheduled_start": from_start.isoformat(),
            "displacement_count": appt.displacement_count,
        }
        appt.scheduled_start = to_start
        appt.scheduled_end = to_start + duration
        appt.displacement_count += 1
        appt.version += 1
        db.flush()
        db.add(
            AppointmentDisplacement(
                appointment_id=appt.id,
                decision_id=record.id,
                from_start=from_start,
                to_start=to_start,
                reason=reason,
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

    emergency = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        type_id=type_id,
        scheduled_start=start,
        scheduled_end=end,
        status=AppointmentStatus.BOOKED,
        origin=AppointmentOrigin.EMERGENCY,
        acuity=acuity,
        displacement_count=0,
        version=1,
    )
    db.add(emergency)
    db.flush()
    record.emergency_appointment_id = emergency.id
    record_audit(
        db,
        entity_type="appointment",
        entity_id=emergency.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        after={"origin": "emergency", "acuity": acuity.value},
        reason="emergency_insertion",
    )
    return emergency


def commit_emergency(
    db: Session,
    *,
    actor_id: int,
    patient_id: int,
    type_id: int,
    acuity: Acuity,
    fingerprint: str,
    idempotency_key: str | None = None,
    plan_digest_value: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply the plan atomically — but only when the engine auto-approves."""
    rhash = request_hash(actor_id, patient_id, type_id, acuity.value)
    replay = _replay(db, idempotency_key, rhash)
    if replay is not None:
        return replay

    patient, appt_type = _resolve(db, patient_id, type_id)
    at = resolve_now(now)
    triage = _require_matching_triage(db, patient_id, acuity, at)

    # Only reachable with a client clock (tests / pinned E2E): reject a commit
    # whose reviewed plan has gone stale on the wall clock.
    if utcnow() - at > PLAN_MAX_AGE:
        raise ConflictError(
            "This plan has expired; please re-plan before committing.",
            details={"code": "plan_expired"},
        )

    doctor_ids = eligible_doctor_ids(db, appt_type.specialty, at)
    # Serialise writers per doctor, then lock the rows we re-read.
    lock_doctors(db, doctor_ids)
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

    # The plan is recomputed on the server's clock; if it no longer matches what
    # the reviewer approved (e.g. the 15-minute grid ticked over), refuse.
    if plan_digest_value is not None and plan_digest(decision_dict["chosen"]) != plan_digest_value:
        raise ConflictError(
            "The proposed plan changed since it was reviewed; please re-plan.",
            details={"code": "plan_changed"},
        )

    snapshot = _snapshot(fingerprint, appts, type_id=type_id, acuity=acuity)

    try:
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
                request_hash=rhash,
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
        record = SchedulingDecision(
            trigger=_TRIGGER,
            status="auto_committed",
            engine_version=decision.engine_version,
            actor_id=actor_id,
            patient_id=patient_id,
            emergency_appointment_id=None,
            idempotency_key=idempotency_key,
            request_hash=rhash,
            input_snapshot=snapshot,
            chosen_plan=decision_dict["chosen"],
            alternatives=decision_dict["alternatives"],
            parameters=decision_dict["parameters"],
            reasons=[],
        )
        db.add(record)
        db.flush()
        moves: list[tuple[int, datetime, str]] = []
        for m in chosen.moves:
            assert m.to_start is not None  # feasible plans never drop an appointment
            moves.append((m.appointment_id, m.to_start, m.reason))
        _apply_plan(
            db,
            record=record,
            actor_id=actor_id,
            patient_id=patient_id,
            type_id=type_id,
            acuity=acuity,
            doctor_id=chosen.placement.doctor_id,
            start=chosen.placement.start,
            end=chosen.placement.end,
            moves=moves,
            by_id={a.id: a for a in appts},
        )
        triage.consumed_at = utcnow()
        db.commit()
        return _commit_result(db, record)
    except IntegrityError:
        db.rollback()
        # Concurrent duplicate of the same request → return the winner's result.
        replay = _replay(db, idempotency_key, rhash)
        if replay is not None:
            return replay
        # Otherwise the database overlap guard refused the write: the schedule
        # moved under us. Safe failure: nothing was applied.
        raise ConflictError(
            "The schedule changed while committing; please re-plan.",
            details={"code": "schedule_changed"},
        ) from None


# --- escalation: review and apply a clinician-approved option ----------------


def _escalation_record(db: Session, decision_id: int, *, lock: bool) -> SchedulingDecision:
    record = db.get(SchedulingDecision, decision_id, with_for_update=lock)
    if record is None:
        raise NotFoundError("Decision not found")
    if record.status != "escalated":
        raise ConflictError(
            "Only escalated decisions have options to apply.",
            details={"code": "not_escalated"},
        )
    if record.resolved_at is not None:
        raise ConflictError(
            "This escalation has already been resolved.",
            details={"code": "already_resolved"},
        )
    return record


def _options(record: SchedulingDecision) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if record.chosen_plan:
        options.append(record.chosen_plan)
    options.extend(record.alternatives or [])
    return options


def escalation_options(db: Session, decision_id: int) -> dict[str, Any]:
    """The options a clinician can choose between for an unresolved escalation."""
    record = _escalation_record(db, decision_id, lock=False)
    options = _options(record)
    appt_ids = {m["appointment_id"] for o in options for m in o["moves"]}
    doctor_ids = list({o["placement"]["doctor_id"] for o in options})
    doctor_rows = (
        list(db.scalars(select(User).where(User.id.in_(doctor_ids)))) if doctor_ids else []
    )
    patient = db.get(Patient, record.patient_id)
    return {
        "decision_id": record.id,
        "reasons": list(record.reasons or []),
        "emergency_patient": {
            "id": record.patient_id,
            "name": patient.name if patient else "",
            "mrn": patient.mrn if patient else "",
        },
        "options": [
            {"index": i, "applicable": bool(o["feasible"]), **o} for i, o in enumerate(options)
        ],
        "appointment_details": _appointment_details(db, appt_ids),
        "doctor_names": {str(u.id): u.name for u in doctor_rows},
    }


def apply_escalated_option(
    db: Session,
    *,
    decision_id: int,
    option_index: int,
    actor_id: int,
    note: str | None = None,
) -> dict[str, Any]:
    """Apply a clinician-approved option from an escalated decision.

    The reviewed option is **recomputed against the live schedule** (all hard
    constraints re-checked) and must reproduce exactly the same placement and
    moves; any drift — schedule change, a consultation started, a patient already
    booked elsewhere — refuses the apply and the nurse re-plans. The patient's
    triage is consumed, so one assessment still authorises one insertion.
    """
    record = _escalation_record(db, decision_id, lock=True)
    options = _options(record)
    if option_index < 0 or option_index >= len(options):
        raise ValidationError("Unknown option for this escalation.")
    option = options[option_index]
    if not option["feasible"]:
        raise ValidationError(
            "This option violates a safety constraint and cannot be applied automatically; "
            "handle it manually and resolve with a note.",
            details={"code": "option_not_applicable", "reject_reasons": option["reject_reasons"]},
        )
    req = (record.input_snapshot or {}).get("request")
    if not req:
        raise ValidationError(
            "This legacy escalation cannot be applied; resolve it with a note.",
            details={"code": "option_not_applicable"},
        )
    type_id = int(req["type_id"])
    acuity = Acuity(req["acuity"])
    patient_id = record.patient_id

    _, appt_type = _resolve(db, patient_id, type_id)
    at = utcnow()
    triage = _require_matching_triage(db, patient_id, acuity, at)

    placement = option["placement"]
    doctor_id = int(placement["doctor_id"])
    start = ensure_aware_utc(datetime.fromisoformat(placement["start"]))
    if at - start > PLAN_MAX_AGE:
        raise ConflictError(
            "This option has expired; please re-plan the emergency.",
            details={"code": "plan_expired"},
        )

    doctor_ids = eligible_doctor_ids(db, appt_type.specialty, at)
    if doctor_id not in doctor_ids:
        raise ConflictError(
            "The doctor is no longer available; please re-plan.",
            details={"code": "schedule_changed"},
        )
    lock_doctors(db, doctor_ids)
    appts = active_appointments(db, doctor_ids, at, for_update=True)
    state = build_engine_state(db, doctor_ids, at, appts, emergency_patient_id=patient_id)
    request = EngineRequest(
        patient_id=patient_id,
        acuity=acuity,
        duration_min=appt_type.default_duration_min,
        eligible_doctor_ids=tuple(doctor_ids),
        now=at,
    )
    rebuilt = plan_at(state, request, doctor_id, start)
    expected_moves = sorted((m["appointment_id"], m["to_start"]) for m in option["moves"])
    if (
        rebuilt is None
        or not rebuilt.feasible
        or sorted(
            (m.appointment_id, m.to_start.isoformat() if m.to_start else None)
            for m in rebuilt.moves
        )
        != expected_moves
    ):
        raise ConflictError(
            "The schedule changed since this option was proposed; please re-plan.",
            details={"code": "schedule_changed"},
        )

    try:
        moves = []
        for m in rebuilt.moves:
            assert m.to_start is not None
            moves.append((m.appointment_id, m.to_start, m.reason))
        emergency = _apply_plan(
            db,
            record=record,
            actor_id=actor_id,
            patient_id=patient_id,
            type_id=type_id,
            acuity=acuity,
            doctor_id=doctor_id,
            start=rebuilt.placement.start,
            end=rebuilt.placement.end,
            moves=moves,
            by_id={a.id: a for a in appts},
        )
        triage.consumed_at = utcnow()
        record.resolved_at = utcnow()
        record.resolved_by = actor_id
        text_note = f"Applied option {option_index + 1}" + (f": {note}" if note else "")
        record.resolution_note = text_note[:500]
        record_audit(
            db,
            entity_type="scheduling_decision",
            entity_id=record.id,
            action=AuditAction.RESOLVE,
            actor_id=actor_id,
            after={"applied_option": option_index, "emergency_appointment_id": emergency.id},
            reason=record.resolution_note,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            "The schedule changed while applying; please re-plan.",
            details={"code": "schedule_changed"},
        ) from None
    result = _commit_result(db, record)
    result["status"] = "applied"
    return result


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
