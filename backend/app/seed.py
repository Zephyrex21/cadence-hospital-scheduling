"""Seed synthetic staff, patients, and scheduling data for development.

Run with: ``python -m app.seed`` (after ``alembic upgrade head``).
Idempotent — rows are keyed by natural keys, so re-running does not duplicate.
All data here is synthetic and for development only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.enums import AppointmentOrigin, AppointmentStatus, Role
from app.core.security import hash_password
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.user import User

# The well-known demo password is for LOCAL development only. Anywhere real,
# set CADENCE_SEED_PASSWORD (required when CADENCE_ENV=production); setting it also
# rotates the password of already-seeded staff accounts.
_DEV_PASSWORD = "cadence123"

# (name, email, role)
_STAFF = [
    ("Rosa Mendez", "receptionist@cadence.dev", Role.RECEPTIONIST),
    ("Theo Park", "nurse@cadence.dev", Role.TRIAGE_NURSE),
    ("Dr. Amara Osei", "doctor@cadence.dev", Role.DOCTOR),
    ("Dr. Luis Rivera", "doctor2@cadence.dev", Role.DOCTOR),
    ("Admin User", "admin@cadence.dev", Role.ADMINISTRATOR),
]

# Seeded shifts cover this many days ahead, so a long-lived demo never runs dry.
_SHIFT_DAYS = 14

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


def _today_at(hour: int, minute: int = 0, *, plus_days: int = 0) -> datetime:
    now = datetime.now(UTC) + timedelta(days=plus_days)
    return datetime(now.year, now.month, now.day, hour, minute, tzinfo=UTC)


def _seed_password() -> str:
    if settings.seed_password:
        return settings.seed_password
    if settings.is_production:
        raise SystemExit(
            "Refusing to seed demo accounts in production without CADENCE_SEED_PASSWORD."
        )
    return _DEV_PASSWORD


def _ensure_staff(db, password: str) -> None:  # type: ignore[no-untyped-def]
    for name, email, role in _STAFF:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(User(name=name, email=email, role=role, password_hash=hash_password(password)))
        elif settings.seed_password:
            user.password_hash = hash_password(password)


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
        # Morning + afternoon shifts for the next two weeks (UTC).
        for day in range(_SHIFT_DAYS):
            for start_h, end_h in ((9, 12), (13, 17)):
                start = _today_at(start_h, plus_days=day)
                end = _today_at(end_h, plus_days=day)
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
    password = _seed_password()
    db = SessionLocal()
    try:
        _ensure_staff(db, password)
        _ensure_patients(db)
        _ensure_types(db)
        db.flush()  # ensure users/patients/types have ids for the next steps
        _ensure_doctor_profiles_and_shifts(db)
        db.flush()
        _ensure_sample_appointments(db)
        db.commit()
        if settings.is_production or settings.seed_password:
            print("Seed complete (staff password taken from CADENCE_SEED_PASSWORD).")
        else:
            print(f"Seed complete. Development staff password: {_DEV_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
