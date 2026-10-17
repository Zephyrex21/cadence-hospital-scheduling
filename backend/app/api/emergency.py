"""Triage and emergency-scheduling endpoints.

* ``POST /triage`` — a nurse records acuity (the clinical judgment).
* ``POST /emergencies/plan`` — dry-run; returns the proposed plan for review.
* ``POST /emergencies/commit`` — applies the plan (transactional, idempotent),
  or surfaces an escalation without touching the schedule.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_roles
from app.core.enums import Role
from app.models.user import User
from app.schemas.emergency import CommitRequest, CommitResponse, PlanRequest, PlanResponse
from app.schemas.triage import TriageCreate, TriageRead
from app.services.emergency import commit_emergency, create_triage, latest_triage, plan_emergency

router = APIRouter(tags=["emergency"])

TRIAGE_ROLES = (Role.TRIAGE_NURSE, Role.ADMINISTRATOR)
EMERGENCY_ROLES = (Role.RECEPTIONIST, Role.TRIAGE_NURSE, Role.ADMINISTRATOR)


@router.post("/triage", response_model=TriageRead, status_code=status.HTTP_201_CREATED)
def record_triage(
    body: TriageCreate,
    db: Session = Depends(get_db),
    nurse: User = Depends(require_roles(*TRIAGE_ROLES)),
) -> TriageRead:
    assessment = create_triage(
        db,
        patient_id=body.patient_id,
        nurse_id=nurse.id,
        acuity=body.acuity,
        chief_complaint=body.chief_complaint,
        vitals=body.vitals,
    )
    return TriageRead.model_validate(assessment)


@router.get("/patients/{patient_id}/latest-triage", response_model=TriageRead | None)
def get_latest_triage(
    patient_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*EMERGENCY_ROLES)),
) -> TriageRead | None:
    """The patient's current (within-window) triage, so a receptionist sees the
    nurse's recorded acuity read-only — or nothing, meaning triage is required."""
    row = latest_triage(db, patient_id)
    return TriageRead.model_validate(row) if row is not None else None


@router.post("/emergencies/plan", response_model=PlanResponse)
def plan(
    body: PlanRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*EMERGENCY_ROLES)),
) -> PlanResponse:
    result = plan_emergency(
        db,
        patient_id=body.patient_id,
        type_id=body.type_id,
        acuity=body.acuity,
        now=body.now,
    )
    return PlanResponse.model_validate(result)


@router.post("/emergencies/commit", response_model=CommitResponse)
def commit(
    body: CommitRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*EMERGENCY_ROLES)),
) -> CommitResponse:
    result = commit_emergency(
        db,
        actor_id=actor.id,
        patient_id=body.patient_id,
        type_id=body.type_id,
        acuity=body.acuity,
        fingerprint=body.fingerprint,
        idempotency_key=body.idempotency_key,
        now=body.now,
    )
    return CommitResponse.model_validate(result)
