"""Patient service: registration and lookup."""

from __future__ import annotations

import secrets

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.enums import AuditAction
from app.core.errors import ConflictError, NotFoundError
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.services.audit import record_audit

_MRN_ATTEMPTS = 5


def _generate_mrn() -> str:
    return f"CAD-{secrets.randbelow(1_000_000):06d}"


def create_patient(db: Session, data: PatientCreate, *, actor_id: int) -> Patient:
    mrn: str | None = None
    for _ in range(_MRN_ATTEMPTS):
        candidate = _generate_mrn()
        if db.scalar(select(Patient.id).where(Patient.mrn == candidate)) is None:
            mrn = candidate
            break
    if mrn is None:
        raise ConflictError("Could not allocate a unique MRN; please retry")

    patient = Patient(
        mrn=mrn,
        name=data.name,
        date_of_birth=data.date_of_birth,
        sex=data.sex,
        contact=data.contact,
    )
    db.add(patient)
    db.flush()  # assigns patient.id

    record_audit(
        db,
        entity_type="patient",
        entity_id=patient.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        after={"mrn": patient.mrn, "name": patient.name},
    )

    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise NotFoundError("Patient not found")
    return patient


def search_patients(db: Session, query: str | None, *, limit: int = 50) -> list[Patient]:
    stmt = select(Patient).order_by(Patient.name)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(or_(Patient.name.ilike(like), Patient.mrn.ilike(like)))
    return list(db.scalars(stmt.limit(limit)))
