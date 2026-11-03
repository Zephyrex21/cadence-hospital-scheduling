"""Profile endpoints (MongoDB-backed): patient profiles and the staff directory."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.enums import Role
from app.core.mongo import get_mongo_db
from app.models.user import User
from app.mongo.models import PatientProfileUpdate, StaffProfileUpdate
from app.schemas.patient import PatientRead
from app.services import profiles as svc

router = APIRouter(tags=["profiles"])


class PatientProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool  # is MongoDB configured at all?
    available: bool  # …and did it answer?
    patient: PatientRead
    profile: dict[str, Any] | None


class StaffUser(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: Role
    is_active: bool
    specialty: str | None = None


class StaffEntry(BaseModel):
    user: StaffUser
    profile: dict[str, Any] | None


@router.get("/patients/{patient_id}/profile", response_model=PatientProfileResponse)
def read_patient_profile(
    patient_id: int,
    db: Session = Depends(get_db),
    mdb: Any = Depends(get_mongo_db),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    return svc.patient_profile_view(db, mdb, patient_id)


@router.put("/patients/{patient_id}/profile", response_model=PatientProfileResponse)
def update_patient_profile(
    patient_id: int,
    body: PatientProfileUpdate,
    db: Session = Depends(get_db),
    mdb: Any = Depends(get_mongo_db),
    actor: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Replaces the sections sent; which sections you may write depends on your role."""
    return svc.update_patient_profile(db, mdb, patient_id, body, actor=actor)


@router.get("/staff", response_model=list[StaffEntry])
def list_staff(
    db: Session = Depends(get_db),
    mdb: Any = Depends(get_mongo_db),
    _: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return svc.list_staff(db, mdb)


@router.get("/staff/{user_id}", response_model=StaffEntry)
def read_staff(
    user_id: int,
    db: Session = Depends(get_db),
    mdb: Any = Depends(get_mongo_db),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    return svc.get_staff(db, mdb, user_id)


@router.put("/staff/{user_id}/profile", response_model=StaffEntry)
def update_staff_profile(
    user_id: int,
    body: StaffProfileUpdate,
    db: Session = Depends(get_db),
    mdb: Any = Depends(get_mongo_db),
    actor: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Admins edit any profile; everyone else only their own contact + languages."""
    return svc.update_staff_profile(db, mdb, user_id, body, actor=actor)
