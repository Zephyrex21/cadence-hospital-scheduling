"""Demo profile content for the MongoDB store (all data is fictitious).

Extends the Postgres demo seed with the structured detail that lives in MongoDB. It only
fills in sections that are *missing*, so profile edits made through the app survive every
restart (unlike the Postgres demo rows, which are refreshed in place).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.user import User
from app.mongo import repo
from app.services.profiles import sections_from_legacy


def _patient(
    city: str, line1: str, state: str, pin: str, language: str, occupation: str,
    *, conditions: tuple[str, ...] = (), allergies: tuple[tuple[str, str, str], ...] = (),
    meds: tuple[tuple[str, str, str], ...] = (), scheme: str = "none", provider: str | None = None,
    abha: str | None = None,
) -> dict[str, Any]:
    sections: dict[str, Any] = {
        "demographics": {"preferred_language": language, "occupation": occupation},
        "address": {"line1": line1, "city": city, "state": state, "pin_code": pin, "country": "IN"},
        "medical": {
            "conditions": list(conditions),
            "allergies": [{"substance": s, "reaction": r, "severity": v} for s, r, v in allergies],
            "medications": [{"name": n, "dose": d, "frequency": f} for n, d, f in meds],
        },
        "insurance": {"scheme": scheme, **({"provider": provider} if provider else {})},
    }
    if abha:
        sections["identifiers"] = {"abha_id": abha}
    return sections


_PATIENT_EXTRAS: dict[str, dict[str, Any]] = {
    "CAD-100001": _patient("New Delhi", "B-42, Janakpuri", "Delhi", "110058", "hi", "Shopkeeper",
                           conditions=("Type 2 diabetes",), meds=(("Metformin", "500 mg", "BD"),),
                           scheme="private", provider="Star Health"),
    "CAD-100002": _patient("Bengaluru", "14, 5th Cross, Indiranagar", "Karnataka", "560038", "en",
                           "Software engineer", scheme="private", provider="HDFC Ergo"),
    "CAD-100003": _patient("Hyderabad", "8-2-120, Banjara Hills", "Telangana", "500034", "ur",
                           "Accountant", allergies=(("Penicillin", "Skin rash", "moderate"),)),
    "CAD-100004": _patient("Kolkata", "22, Gariahat Road", "West Bengal", "700019", "bn", "Teacher",
                           scheme="esi"),
    "CAD-100005": _patient("Ludhiana", "H.No. 310, Model Town", "Punjab", "141002", "pa", "Farmer",
                           conditions=("Hypertension",), meds=(("Amlodipine", "5 mg", "OD"),),
                           scheme="cghs", abha="91-1234-5678-9012"),
    "CAD-100006": _patient("Chennai", "7, Gandhi Street, T. Nagar", "Tamil Nadu", "600017", "ta",
                           "Retired teacher", conditions=("Coronary artery disease",),
                           meds=(("Aspirin", "75 mg", "OD"), ("Atorvastatin", "20 mg", "HS")),
                           scheme="ayushman_bharat", abha="91-9876-5432-1098"),
    "CAD-100007": _patient("Pune", "Flat 5, Sai Heights, Kothrud", "Maharashtra", "411038", "mr",
                           "Student"),
    "CAD-100008": _patient("Mumbai", "Pali Hill, Bandra West", "Maharashtra", "400050", "hi",
                           "Designer", scheme="private", provider="Niva Bupa"),
    "CAD-100009": _patient("Ahmedabad", "12, Navrangpura", "Gujarat", "380009", "gu", "Student",
                           conditions=("Asthma (mild)",),
                           meds=(("Salbutamol inhaler", "100 mcg", "SOS"),)),
    "CAD-100010": _patient("Vijayawada", "Benz Circle", "Andhra Pradesh", "520010", "te",
                           "Homemaker", scheme="private", provider="Care Health"),
}


def _qual(degree: str, institution: str, year: int) -> dict[str, Any]:
    return {"degree": degree, "institution": institution, "year": year}


_STAFF_EXTRAS: dict[str, dict[str, Any]] = {
    "receptionist@cadence.dev": {
        "employee_id": "REC-001", "department": "Front desk", "languages": ["en", "hi"],
        "contact": {"phone": "+91 90000 30001"},
        "employment": {"joined_on": date(2021, 6, 1).isoformat(), "status": "active"},
        "reception": {"counter": "Front desk 1", "shift_pattern": "day",
                      "training": ["Patient registration", "Triage handoff"]},
    },
    "nurse@cadence.dev": {
        "employee_id": "NUR-001", "department": "Emergency & triage",
        "languages": ["en", "hi", "pa"], "contact": {"phone": "+91 90000 30002"},
        "employment": {"joined_on": date(2019, 2, 11).isoformat(), "status": "active"},
        "nurse": {
            "registration": {"council": "Delhi Nursing Council", "number": "DNC-48213"},
            "qualifications": [_qual("B.Sc Nursing", "AIIMS College of Nursing", 2016)],
            "certifications": [
                {"name": "BLS", "expires_on": date(2027, 3, 31).isoformat()},
                {"name": "ACLS", "expires_on": date(2027, 9, 30).isoformat()},
                {"name": "Emergency triage", "expires_on": date(2028, 1, 31).isoformat()},
            ],
            "ward": "Emergency", "shift_pattern": "rotating",
        },
    },
    "doctor@cadence.dev": {
        "employee_id": "DOC-001", "department": "General Medicine", "languages": ["en", "hi"],
        "contact": {"phone": "+91 90000 30003"},
        "employment": {"joined_on": date(2018, 4, 2).isoformat(), "status": "active"},
        "doctor": {
            "registration": {"council": "Delhi Medical Council", "number": "DMC-31877"},
            "qualifications": [_qual("MBBS", "Maulana Azad Medical College", 2009),
                               _qual("MD (Medicine)", "AIIMS Delhi", 2013)],
            "sub_specialties": ["Diabetology"], "experience_years": 13,
            "consultation_fee_inr": 600,
            "bio": "General physician with a focus on diabetes and lifestyle disease.",
        },
    },
    "doctor2@cadence.dev": {
        "employee_id": "DOC-002", "department": "General Medicine",
        "languages": ["en", "hi", "gu"], "contact": {"phone": "+91 90000 30004"},
        "employment": {"joined_on": date(2016, 8, 16).isoformat(), "status": "active"},
        "doctor": {
            "registration": {"council": "Delhi Medical Council", "number": "DMC-27450"},
            "qualifications": [_qual("MBBS", "Grant Medical College, Mumbai", 2007),
                               _qual("DNB (Family Medicine)", "National Board of Exams", 2011)],
            "sub_specialties": ["Geriatrics"], "experience_years": 15, "consultation_fee_inr": 600,
        },
    },
    "doctor3@cadence.dev": {
        "employee_id": "DOC-003", "department": "Cardiology", "languages": ["en", "ml", "hi"],
        "contact": {"phone": "+91 90000 30005"},
        "employment": {"joined_on": date(2020, 1, 20).isoformat(), "status": "active"},
        "doctor": {
            "registration": {"council": "Delhi Medical Council", "number": "DMC-35192"},
            "qualifications": [_qual("MBBS", "Government Medical College, Kozhikode", 2010),
                               _qual("DM (Cardiology)", "AIIMS Delhi", 2017)],
            "sub_specialties": ["Interventional cardiology", "Heart failure"],
            "experience_years": 11, "consultation_fee_inr": 1000,
        },
    },
    "admin@cadence.dev": {
        "employee_id": "ADM-001", "department": "Administration",
        "languages": ["en", "hi", "pa"], "contact": {"phone": "+91 90000 30006"},
        "employment": {"joined_on": date(2017, 5, 8).isoformat(), "status": "active"},
    },
}


def _merge(legacy: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(legacy)
    for key, value in extra.items():
        base = merged.get(key)
        if isinstance(base, dict) and isinstance(value, dict):
            merged[key] = {**base, **value}
        else:
            merged[key] = value
    return merged


def seed_profiles(db: Session, mdb: Any) -> None:
    """Create rich demo profiles; sections that already exist are never overwritten."""
    patients = {p.mrn: p for p in db.scalars(select(Patient))}
    for mrn, extra in _PATIENT_EXTRAS.items():
        patient = patients.get(mrn)
        if patient is None:
            continue
        wanted = _merge(sections_from_legacy(patient), extra)
        existing = repo.get_patient_doc(mdb, patient.id) or {}
        missing = {k: v for k, v in wanted.items() if k not in existing}
        if missing or not existing:
            repo.upsert_patient_doc(mdb, patient_id=patient.id, mrn=patient.mrn,
                                    sections=missing, actor_id=None)

    users = {u.email: u for u in db.scalars(select(User))}
    for email, wanted_staff in _STAFF_EXTRAS.items():
        user = users.get(email)
        if user is None:
            continue
        existing_staff = repo.get_staff_doc(mdb, user.id) or {}
        missing_staff = {k: v for k, v in wanted_staff.items() if k not in existing_staff}
        if missing_staff or not existing_staff:
            repo.upsert_staff_doc(mdb, user_id=user.id, role=user.role.value,
                                  sections=missing_staff, actor_id=None)
