"""Seed synthetic staff, patients, and scheduling data for development.

Run with: ``python -m app.seed`` (after ``alembic upgrade head``).
Idempotent — rows are keyed by natural keys, so re-running does not duplicate.
All data here is synthetic and for development only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.enums import AppointmentOrigin, AppointmentStatus, Role
from app.core.security import hash_password
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.user import User

# (name, email, role, password) — development credentials only.
_STAFF = [
    ("Rosa Mendez", "receptionist@cadence.dev", Role.RECEPTIONIST, "cadence123"),
    ("Theo Park", "nurse@cadence.dev", Role.TRIAGE_NURSE, "cadence123"),
    ("Dr. Amara Osei", "doctor@cadence.dev", Role.DOCTOR, "cadence123"),
    ("Dr. Luis Rivera", "doctor2@cadence.dev", Role.DOCTOR, "cadence123"),
    ("Admin User", "admin@cadence.dev", Role.ADMINISTRATOR, "cadence123"),
]

_PATIENTS = [
    ("CAD-100001", "John Carter", date(1980, 4, 12), "male", "555-0101"),
    ("CAD-100002", "Maria Lopez", date(1992, 9, 3), "female", "555-0102"),
    ("CAD-100003", "Wei Chen", date(1975, 1, 27), "male", "555-0103"),
]

# (name, default_duration_min, specialty)
_TYPES = [
    ("General consultation", 30, "general"),
    ("Follow-up", 15, "general"),
    ("Extended consultation", 45, "general"),
]

_DOCTOR_EMAILS = ["doctor@cadence.dev", "doctor2@cadence.dev"]


def _today_at(hour: int, minute: int = 0) -> datetime:
    now = datetime.now(UTC)
    return datetime(now.year, now.month, now.day, hour, minute, tzinfo=UTC)


def _ensure_staff(db) -> None:  # type: ignore[no-untyped-def]
    for name, email, role, password in _STAFF:
        if db.scalar(select(User).where(User.email == email)) is None:
            db.add(User(name=name, email=email, role=role, password_hash=hash_password(password)))


def _ensure_patients(db) -> None:  # type: ignore[no-untyped-def]
    for mrn, name, dob, sex, contact in _PATIENTS:
        if db.scalar(select(Patient).where(Patient.mrn == mrn)) is None:
            db.add(Patient(mrn=mrn, name=name, date_of_birth=dob, sex=sex, contact=contact))


def _ensure_types(db) -> None:  # type: ignore[no-untyped-def]
    for name, duration, specialty in _TYPES:
        if db.scalar(select(AppointmentType).where(AppointmentType.name == name)) is None:
            db.add(
                AppointmentType(
                    name=name, default_duration_min=duration, specialty=specialty
                )
            )


def _ensure_doctor_profiles_and_shifts(db) -> None:  # type: ignore[no-untyped-def]
    for email in _DOCTOR_EMAILS:
        doctor = db.scalar(select(User).where(User.email == email))
        if doctor is None:
            continue
        if db.get(DoctorProfile, doctor.id) is None:
            db.add(DoctorProfile(user_id=doctor.id, specialty="general"))
        # Morning + afternoon shift for today (UTC).
        for start_h, end_h in ((9, 12), (13, 17)):
            start, end = _today_at(start_h), _today_at(end_h)
            exists = db.scalar(
                select(Shift).where(Shift.doctor_id == doctor.id, Shift.start_utc == start)
            )
            if exists is None:
                db.add(Shift(doctor_id=doctor.id, start_utc=start, end_utc=end))


def _ensure_sample_appointments(db) -> None:  # type: ignore[no-untyped-def]
    doctor = db.scalar(select(User).where(User.email == "doctor@cadence.dev"))
    general = db.scalar(
        select(AppointmentType).where(AppointmentType.name == "General consultation")
    )
    followup = db.scalar(select(AppointmentType).where(AppointmentType.name == "Follow-up"))
    john = db.scalar(select(Patient).where(Patient.mrn == "CAD-100001"))
    maria = db.scalar(select(Patient).where(Patient.mrn == "CAD-100002"))
    if not all((doctor, general, followup, john, maria)):
        return

    plan = [
        (john, general, _today_at(9, 0)),
        (maria, followup, _today_at(10, 0)),
    ]
    for patient, appt_type, start in plan:
        exists = db.scalar(
            select(Appointment).where(
                Appointment.doctor_id == doctor.id, Appointment.scheduled_start == start
            )
        )
        if exists is None:
            db.add(
                Appointment(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    type_id=appt_type.id,
                    scheduled_start=start,
                    scheduled_end=start + timedelta(minutes=appt_type.default_duration_min),
                    status=AppointmentStatus.BOOKED,
                    origin=AppointmentOrigin.BOOKED,
                    version=1,
                )
            )


def seed() -> None:
    db = SessionLocal()
    try:
        _ensure_staff(db)
        _ensure_patients(db)
        _ensure_types(db)
        db.flush()  # ensure users/patients/types have ids for the next steps
        _ensure_doctor_profiles_and_shifts(db)
        db.flush()
        _ensure_sample_appointments(db)
        db.commit()
        print("Seed complete. Staff password for all accounts: cadence123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
