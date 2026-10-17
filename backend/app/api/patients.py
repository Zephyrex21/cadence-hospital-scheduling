"""Patient endpoints: list/search, register, and read-by-id."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_roles
from app.core.enums import Role
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientRead
from app.services.patients import create_patient, get_patient, search_patients

router = APIRouter(prefix="/patients", tags=["patients"])

# Doctors do not register patients; everyone authenticated may read.
WRITE_ROLES = (Role.RECEPTIONIST, Role.TRIAGE_NURSE, Role.ADMINISTRATOR)


@router.get("", response_model=list[PatientRead])
def list_patients(
    q: str | None = Query(default=None, description="Search by name or MRN"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Patient]:
    return search_patients(db, q)


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def register_patient(
    body: PatientCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(*WRITE_ROLES)),
) -> Patient:
    return create_patient(db, body, actor_id=actor.id)


@router.get("/{patient_id}", response_model=PatientRead)
def read_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Patient:
    return get_patient(db, patient_id)
