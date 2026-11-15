"""Queue and consultation-status endpoints.

* ``GET /queue`` — prioritized waiting list with wait estimates (any staff).
* ``POST /appointments/{id}/status`` — doctor/admin consultation transitions.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.clock import resolve_now
from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.enums import Role
from app.models.user import User
from app.schemas.consultation import (
    ExtendRequest,
    ExtendResponse,
    QueueEntryOut,
    StatusChangeRequest,
    StatusChangeResponse,
)
from app.services.consultation import change_consultation_status, list_queue
from app.services.notifications import dispatch_queued
from app.services.overrun import extend_consultation

router = APIRouter(tags=["consultation"])

# Every staff role may call it; the service decides which *action* each role may perform.
STATUS_ROLES = (Role.DOCTOR, Role.ADMINISTRATOR, Role.RECEPTIONIST, Role.TRIAGE_NURSE)


@router.get("/queue", response_model=list[QueueEntryOut])
def get_queue(
    doctor_id: int | None = Query(default=None),
    now: datetime | None = Query(default=None, description="Defaults to current UTC time."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[QueueEntryOut]:
    entries = list_queue(db, resolve_now(now), doctor_id)
    return [QueueEntryOut.model_validate(e) for e in entries]


@router.post("/appointments/{appointment_id}/status", response_model=StatusChangeResponse)
def change_status(
    appointment_id: int,
    body: StatusChangeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*STATUS_ROLES)),
) -> StatusChangeResponse:
    appt = change_consultation_status(
        db, appointment_id, body.action, actor=actor, expected_version=body.version
    )
    return StatusChangeResponse(id=appt.id, status=appt.status, version=appt.version)


@router.post("/appointments/{appointment_id}/extend", response_model=ExtendResponse)
def extend(
    appointment_id: int,
    body: ExtendRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.DOCTOR, Role.ADMINISTRATOR)),
) -> ExtendResponse:
    """The consultation is running over: extend it and push later patients back."""
    result = extend_consultation(
        db, appointment_id, body.minutes, actor=actor, expected_version=body.version
    )
    dispatch_queued(db)  # tell the patients who were moved; never fails the request
    return ExtendResponse.model_validate(result)
