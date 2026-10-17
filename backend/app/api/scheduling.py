"""Scheduling endpoints: doctors, appointment types, shifts, slots, schedule, booking.

Reads are open to any authenticated user; booking/cancelling is restricted to the
front-desk roles (receptionist, triage nurse, administrator) — doctors manage
consultation status, not the booking ledger.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.enums import Role
from app.models.appointment_type import AppointmentType
from app.models.user import User
from app.schemas.scheduling import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentTypeRead,
    CancelRequest,
    DoctorRead,
    PatientSummary,
    ShiftRead,
    SlotRead,
)
from app.services.scheduling import (
    available_slots,
    book_appointment,
    cancel_appointment,
    list_appointment_types,
    list_doctors,
    list_schedule,
    list_shifts,
)

router = APIRouter(tags=["scheduling"])

BOOK_ROLES = (Role.RECEPTIONIST, Role.TRIAGE_NURSE, Role.ADMINISTRATOR)


def _serialize(appt) -> AppointmentRead:  # type: ignore[no-untyped-def]
    """Map an Appointment ORM row (with relations loaded via identity map) to the DTO."""
    return AppointmentRead(
        id=appt.id,
        status=appt.status,
        origin=appt.origin,
        scheduled_start=appt.scheduled_start,
        scheduled_end=appt.scheduled_end,
        version=appt.version,
        patient=PatientSummary(id=appt.patient.id, name=appt.patient.name, mrn=appt.patient.mrn),
        doctor=DoctorRead(id=appt.doctor.id, name=appt.doctor.name, specialty=_specialty(appt)),
        type=AppointmentTypeRead(
            id=appt.type.id,
            name=appt.type.name,
            default_duration_min=appt.type.default_duration_min,
            specialty=appt.type.specialty,
        ),
    )


def _specialty(appt) -> str:  # type: ignore[no-untyped-def]
    profile = getattr(appt.doctor, "doctor_profile", None)
    return profile.specialty if profile else "general"


@router.get("/doctors", response_model=list[DoctorRead])
def get_doctors(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[dict[str, Any]]:
    return list_doctors(db)


@router.get("/appointment-types", response_model=list[AppointmentTypeRead])
def get_types(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AppointmentType]:
    return list_appointment_types(db)


@router.get("/doctors/{doctor_id}/shifts", response_model=list[ShiftRead])
def get_shifts(
    doctor_id: int,
    day: datetime = Query(..., description="Any instant within the target day (UTC)."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ShiftRead]:
    return [
        ShiftRead(id=s.id, doctor_id=s.doctor_id, start=s.start_utc, end=s.end_utc)
        for s in list_shifts(db, doctor_id, day)
    ]


@router.get("/slots", response_model=list[SlotRead])
def get_slots(
    doctor_id: int = Query(...),
    type_id: int = Query(...),
    day: datetime = Query(..., description="Any instant within the target day (UTC)."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SlotRead]:
    return [
        SlotRead(start=iv.start, end=iv.end)
        for iv in available_slots(db, doctor_id, type_id, day)
    ]


@router.get("/schedule", response_model=list[AppointmentRead])
def get_schedule(
    day: datetime = Query(..., description="Any instant within the target day (UTC)."),
    doctor_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AppointmentRead]:
    return [_serialize(a) for a in list_schedule(db, day, doctor_id)]


@router.post("/appointments", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment(
    body: AppointmentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*BOOK_ROLES)),
) -> AppointmentRead:
    return _serialize(book_appointment(db, body, actor_id=actor.id))


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel(
    appointment_id: int,
    body: CancelRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*BOOK_ROLES)),
) -> AppointmentRead:
    appt = cancel_appointment(
        db,
        appointment_id,
        actor_id=actor.id,
        reason=body.reason,
        expected_version=body.version,
    )
    return _serialize(appt)
