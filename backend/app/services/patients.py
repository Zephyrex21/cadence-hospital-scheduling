"""Patient service: registration and lookup."""

from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import AuditAction
from app.core.errors import ConflictError, NotFoundError
from app.core.mongo import get_mongo_db
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.services.audit import record_audit

_MRN_ATTEMPTS = 5


def _generate_mrn() -> str:
    return f"CAD-{secrets.randbelow(1_000_000):06d}"


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def create_patient(db: Session, data: PatientCreate, *, actor_id: int) -> Patient:
    # Allocate the MRN by *inserting* it inside a savepoint and retrying on a collision, rather
    # than checking first: two simultaneous registrations could otherwise both pass the check.
    patient: Patient | None = None
    for _ in range(_MRN_ATTEMPTS):
        candidate = Patient(
            mrn=_generate_mrn(),
            name=data.name.strip(),
            date_of_birth=data.date_of_birth,
            sex=data.sex,
            contact=_clean(data.contact),
            city=_clean(data.city),
            blood_group=_clean(data.blood_group),
            emergency_contact=_clean(data.emergency_contact),
            notes=_clean(data.notes),
        )
        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()  # assigns patient.id; raises if the MRN is taken
        except IntegrityError:
            continue
        patient = candidate
        break
    if patient is None:
        raise ConflictError("Could not allocate a unique MRN; please retry")

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

    # Optional MongoDB profile: created after the Postgres commit and never able to fail it.
    mdb = get_mongo_db()
    if mdb is not None:
        from app.services.profiles import create_base_profile

        create_base_profile(mdb, patient, actor_id=actor_id)
    return patient


def get_patient(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise NotFoundError("Patient not found")
    return patient


def _matching(query: str | None) -> Any:
    stmt = select(Patient)
    if query and query.strip():
        # Treat what the user typed literally: "%" and "_" are not wildcards in a name search.
        escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        stmt = stmt.where(
            or_(
                Patient.name.ilike(like, escape="\\"),
                Patient.mrn.ilike(like, escape="\\"),
                Patient.contact.ilike(like, escape="\\"),
                Patient.city.ilike(like, escape="\\"),
            )
        )
    return stmt


def search_patients(
    db: Session, query: str | None, *, limit: int = 50, offset: int = 0
) -> list[Patient]:
    stmt = _matching(query).order_by(Patient.name, Patient.id).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def count_patients(db: Session, query: str | None) -> int:
    return int(db.scalar(select(func.count()).select_from(_matching(query).subquery())) or 0)
