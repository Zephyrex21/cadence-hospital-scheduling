"""History endpoints.

* ``GET /displacements`` — operational visibility of rescheduled appointments
  (any authenticated staff).
* ``GET /scheduling-decisions`` and ``/{id}`` — the engine's decision trace
  (administrators only — governance).
* ``GET /audit`` — the audit log (administrators only).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.enums import Role
from app.core.errors import NotFoundError
from app.models.user import User
from app.schemas.history import (
    AuditEntryOut,
    DecisionDetailOut,
    DecisionSummaryOut,
    DisplacementOut,
    ResolveRequest,
    ResolveResponse,
)
from app.services.history import (
    get_decision,
    list_audit,
    list_decisions,
    list_displacements,
    resolve_decision,
)

router = APIRouter(tags=["history"])

ADMIN_ONLY = (Role.ADMINISTRATOR,)
# Clinical sign-off on an escalation: a nurse or an administrator.
RESOLVE_ROLES = (Role.TRIAGE_NURSE, Role.ADMINISTRATOR)


@router.get("/displacements", response_model=list[DisplacementOut])
def get_displacements(
    day: datetime | None = Query(default=None, description="Filter to a single day (UTC)."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DisplacementOut]:
    return [DisplacementOut.model_validate(d) for d in list_displacements(db, day)]


@router.get("/scheduling-decisions", response_model=list[DecisionSummaryOut])
def get_decisions(
    day: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ADMIN_ONLY)),
) -> list[DecisionSummaryOut]:
    return [DecisionSummaryOut.model_validate(d) for d in list_decisions(db, day)]


@router.get("/scheduling-decisions/{decision_id}", response_model=DecisionDetailOut)
def get_decision_detail(
    decision_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ADMIN_ONLY)),
) -> DecisionDetailOut:
    detail = get_decision(db, decision_id)
    if detail is None:
        raise NotFoundError("Decision not found")
    return DecisionDetailOut.model_validate(detail)


@router.post("/scheduling-decisions/{decision_id}/resolve", response_model=ResolveResponse)
def resolve_escalation(
    decision_id: int,
    body: ResolveRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*RESOLVE_ROLES)),
) -> ResolveResponse:
    result = resolve_decision(db, decision_id, actor_id=actor.id, note=body.note)
    return ResolveResponse.model_validate(result)


@router.get("/audit", response_model=list[AuditEntryOut])
def get_audit(
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*ADMIN_ONLY)),
) -> list[AuditEntryOut]:
    return [AuditEntryOut.model_validate(a) for a in list_audit(db, entity_type, limit)]
