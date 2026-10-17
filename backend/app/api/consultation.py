"""Queue and consultation-status endpoints.

* ``GET /queue`` — prioritized waiting list with wait estimates (any staff).
* ``POST /appointments/{id}/status`` — doctor/admin consultation transitions.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.enums import Role
from app.models.base import utcnow
from app.models.user import User
from app.schemas.consultation import (
    QueueEntryOut,
    StatusChangeRequest,
    StatusChangeResponse,
)
from app.services.consultation import change_consultation_status, list_queue

router = APIRouter(tags=["consultation"])

STATUS_ROLES = (Role.DOCTOR, Role.ADMINISTRATOR)


@router.get("/queue", response_model=list[QueueEntryOut])
def get_queue(
    doctor_id: int | None = Query(default=None),
    now: datetime | None = Query(default=None, description="Defaults to current UTC time."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[QueueEntryOut]:
    entries = list_queue(db, now or utcnow(), doctor_id)
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
