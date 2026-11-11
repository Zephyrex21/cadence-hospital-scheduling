"""Profile service: patient + staff profiles in MongoDB, layered on Postgres records.

Rules of the road:
* Postgres owns identity, auth, scheduling and the patient search keys; Mongo owns the
  descriptive detail. Reads join the two.
* A profile update validates, writes Mongo, then mirrors the few legacy patient columns
  (contact / city / blood group / emergency contact / notes) that the list + search page
  read, and records an audit row — Postgres commits last, so a Mongo failure changes nothing.
* Mongo being down never breaks registration or reads: it degrades to "no profile".
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from pymongo.errors import DuplicateKeyError, PyMongoError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, Role
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ProfileStoreDisabledError,
    ProfileStoreError,
    ValidationError,
)
from app.models.patient import Patient
from app.models.user import User
from app.mongo import repo
from app.mongo.models import (
    PATIENT_SECTIONS,
    STAFF_SECTIONS,
    PatientProfileUpdate,
    StaffProfileUpdate,
)
from app.services.audit import record_audit
from app.services.patients import get_patient

log = logging.getLogger("uvicorn.error.cadence.profiles")

# Which patient-profile sections each role may write. Doctors are read-only, matching
# the existing rule that doctors don't register or edit patient records.
_ALL_PATIENT = set(PATIENT_SECTIONS)
_PATIENT_WRITE: dict[Role, set[str]] = {
    Role.ADMINISTRATOR: _ALL_PATIENT,
    Role.RECEPTIONIST: {
        "demographics", "contact", "address", "emergency_contacts", "insurance",
        "identifiers", "notes",
    },
    Role.TRIAGE_NURSE: {"medical", "contact", "emergency_contacts", "notes"},
    Role.DOCTOR: set(),
}
# Everyone may edit these on *their own* staff profile; the rest is admin-only.
_STAFF_SELF = {"contact", "languages"}
_ROLE_DETAIL = {
    Role.DOCTOR: "doctor",
    Role.TRIAGE_NURSE: "nurse",
    Role.RECEPTIONIST: "reception",
    Role.ADMINISTRATOR: None,
}


@contextmanager
def _store_errors() -> Iterator[None]:
    try:
        yield
    except DuplicateKeyError as exc:
        # A unique index (employee id, MRN…) was hit: the caller's data is the problem,
        # not the store.
        raise ConflictError("That value is already used by another profile") from exc
    except PyMongoError as exc:
        log.warning("MongoDB operation failed: %s", exc)
        raise ProfileStoreError(
            "The profile store is temporarily unavailable. Please try again."
        ) from exc


def _require(mdb: Any | None) -> Any:
    if mdb is None:
        raise ProfileStoreDisabledError("The profile store (MongoDB) is not configured")
    return mdb


def _sections(body: Any, allowed: tuple[str, ...]) -> dict[str, Any]:
    """The sections the caller actually sent (``None`` = clear)."""
    data = body.model_dump(mode="json", exclude_none=True)
    return {name: data.get(name) for name in body.model_fields_set if name in allowed}


# --- legacy <-> profile --------------------------------------------------------------

_EC = re.compile(r"^(?P<name>[^(·]+?)\s*(?:\((?P<relation>[^)]*)\))?\s*(?:·\s*(?P<phone>.+))?$")


def parse_emergency_contact(text: str | None) -> dict[str, Any] | None:
    """``"Asha Rao (mother) · +91 90000 54321"`` -> structured contact."""
    match = _EC.match((text or "").strip())
    if not match or not match["name"].strip():
        return None
    parsed: dict[str, Any] = {"name": match["name"].strip(), "is_primary": True}
    if match["relation"] and match["relation"].strip():
        parsed["relation"] = match["relation"].strip()
    if match["phone"] and match["phone"].strip():
        parsed["phone"] = match["phone"].strip()
    return parsed


def format_emergency_contact(contact: dict[str, Any]) -> str:
    text = str(contact["name"])
    if contact.get("relation"):
        text += f" ({contact['relation']})"
    if contact.get("phone"):
        text += f" · {contact['phone']}"
    return text[:160]


def sections_from_legacy(patient: Patient) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    if patient.contact:
        key = "email" if "@" in patient.contact else "phone"
        sections["contact"] = {key: patient.contact}
    if patient.city:
        sections["address"] = {"city": patient.city, "country": "IN"}
    if patient.blood_group:
        sections["medical"] = {"blood_group": patient.blood_group, "allergies": [],
                               "conditions": [], "medications": []}
    ec = parse_emergency_contact(patient.emergency_contact)
    if ec:
        sections["emergency_contacts"] = [ec]
    if patient.notes:
        sections["notes"] = patient.notes
    return sections


def _mirror_legacy_columns(patient: Patient, doc: dict[str, Any], touched: set[str]) -> None:
    """Copy *only the sections that were just written* into the legacy columns.

    Mirroring everything from a document that lacks a section would blank the patient's
    existing phone / city / emergency contact / notes (data loss).
    """
    if "contact" in touched:
        contact = doc.get("contact") or {}
        patient.contact = contact.get("phone") or contact.get("email") or None
    if "address" in touched:
        patient.city = (doc.get("address") or {}).get("city") or None
    if "medical" in touched:
        patient.blood_group = (doc.get("medical") or {}).get("blood_group") or None
    if "emergency_contacts" in touched:
        contacts = doc.get("emergency_contacts") or []
        primary = next(
            (c for c in contacts if c.get("is_primary")), contacts[0] if contacts else None
        )
        patient.emergency_contact = format_emergency_contact(primary) if primary else None
    if "notes" in touched:
        patient.notes = (doc.get("notes") or "")[:500] or None


# --- patients ------------------------------------------------------------------------


def patient_profile_view(db: Session, mdb: Any | None, patient_id: int) -> dict[str, Any]:
    patient = get_patient(db, patient_id)  # 404 if unknown
    view: dict[str, Any] = {"enabled": mdb is not None, "available": False, "patient": patient,
                            "profile": None}
    if mdb is None:
        return view
    try:
        view["profile"] = repo.get_patient_doc(mdb, patient_id)
        view["available"] = True
    except PyMongoError as exc:
        log.warning("Could not read patient profile %s: %s", patient_id, exc)
    return view


def update_patient_profile(
    db: Session, mdb: Any | None, patient_id: int, body: PatientProfileUpdate, *, actor: User
) -> dict[str, Any]:
    store = _require(mdb)
    patient = get_patient(db, patient_id)
    sections = _sections(body, PATIENT_SECTIONS)

    denied = set(sections) - _PATIENT_WRITE[actor.role]
    if denied:
        raise ForbiddenError(f"Your role cannot edit: {', '.join(sorted(denied))}")

    with _store_errors():
        if repo.get_patient_doc(store, patient.id) is None:
            # No profile yet (Mongo was down at registration, or enabled later): start from
            # what the patient record already holds, so nothing existing is lost.
            repo.upsert_patient_doc(
                store, patient_id=patient.id, mrn=patient.mrn,
                sections=sections_from_legacy(patient), actor_id=actor.id,
            )
        doc = repo.upsert_patient_doc(
            store, patient_id=patient.id, mrn=patient.mrn, sections=sections, actor_id=actor.id
        )

    _mirror_legacy_columns(patient, doc, set(sections))
    record_audit(
        db,
        entity_type="patient_profile",
        entity_id=patient.id,
        action=AuditAction.UPDATE,
        actor_id=actor.id,
        after={"sections": sorted(sections)},
    )
    db.commit()
    return patient_profile_view(db, store, patient_id)


def create_base_profile(mdb: Any, patient: Patient, *, actor_id: int | None) -> None:
    """Called right after registration. Best-effort: never fails the registration."""
    try:
        repo.upsert_patient_doc(
            mdb, patient_id=patient.id, mrn=patient.mrn,
            sections=sections_from_legacy(patient), actor_id=actor_id,
        )
    except PyMongoError as exc:
        log.warning("Patient %s registered but profile not created (will backfill): %s",
                    patient.id, exc)


# --- staff ---------------------------------------------------------------------------


def _staff_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "specialty": user.doctor_profile.specialty if user.doctor_profile else None,
    }


def list_staff(db: Session, mdb: Any | None) -> list[dict[str, Any]]:
    users = list(db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.name)))
    docs: dict[int, dict[str, Any]] = {}
    if mdb is not None:
        try:
            docs = repo.staff_docs_by_user(mdb)
        except PyMongoError as exc:
            log.warning("Could not read staff profiles: %s", exc)
    return [{"user": _staff_user(u), "profile": docs.get(u.id)} for u in users]


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("Staff member not found")
    return user


def get_staff(db: Session, mdb: Any | None, user_id: int) -> dict[str, Any]:
    user = _get_user(db, user_id)
    profile = None
    if mdb is not None:
        try:
            profile = repo.get_staff_doc(mdb, user_id)
        except PyMongoError as exc:
            log.warning("Could not read staff profile %s: %s", user_id, exc)
    return {"user": _staff_user(user), "profile": profile}


def update_staff_profile(
    db: Session, mdb: Any | None, user_id: int, body: StaffProfileUpdate, *, actor: User
) -> dict[str, Any]:
    store = _require(mdb)
    user = _get_user(db, user_id)
    sections = _sections(body, STAFF_SECTIONS)

    if actor.role != Role.ADMINISTRATOR:
        if actor.id != user.id:
            raise ForbiddenError("You can only edit your own profile")
        denied = set(sections) - _STAFF_SELF
        if denied:
            raise ForbiddenError(f"Only an administrator can edit: {', '.join(sorted(denied))}")

    expected = _ROLE_DETAIL[user.role]
    for detail in ("doctor", "nurse", "reception"):
        if detail in sections and sections[detail] is not None and detail != expected:
            raise ValidationError(f"'{detail}' details don't apply to a {user.role.value}")

    with _store_errors():
        repo.upsert_staff_doc(
            store, user_id=user.id, role=user.role.value, sections=sections, actor_id=actor.id
        )
    record_audit(
        db,
        entity_type="staff_profile",
        entity_id=user.id,
        action=AuditAction.UPDATE,
        actor_id=actor.id,
        after={"sections": sorted(sections)},
    )
    db.commit()
    return get_staff(db, store, user_id)


# --- backfill ------------------------------------------------------------------------


def backfill_profiles(db: Session, mdb: Any) -> dict[str, int]:
    """Create a base profile for every patient / staff member that lacks one.

    Idempotent and non-destructive: existing profiles are left alone. Run at startup so
    records created before MongoDB was enabled (or while it was down) catch up.
    """
    have_patients = repo.patient_ids_with_docs(mdb)
    new_patients = 0
    for patient in db.scalars(select(Patient)):
        if patient.id not in have_patients:
            repo.upsert_patient_doc(mdb, patient_id=patient.id, mrn=patient.mrn,
                                    sections=sections_from_legacy(patient), actor_id=None)
            new_patients += 1

    have_staff = set(repo.staff_docs_by_user(mdb))
    new_staff = 0
    for user in db.scalars(select(User).where(User.is_active.is_(True))):
        if user.id not in have_staff:
            repo.upsert_staff_doc(mdb, user_id=user.id, role=user.role.value, sections={},
                                  actor_id=None)
            new_staff += 1
    return {"patients": new_patients, "staff": new_staff}
