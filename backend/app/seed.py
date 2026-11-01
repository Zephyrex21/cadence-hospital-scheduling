"""Seed demo staff, patients and scheduling data (Indian hospital setting).

Run with: ``python -m app.seed`` (after ``alembic upgrade head``), or set
``CADENCE_SEED_DEMO_ON_START=true`` to refresh it every time the API starts (for
hosts without a shell). Idempotent *upserts* keyed by natural keys (MRN, e-mail,
type name): re-running never duplicates, and records seeded by an older version of
this file (e.g. the previous placeholder names) are **updated in place**, never
wiped. Patients you register yourself are left alone.

All people, numbers and addresses below are fictitious.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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

log = logging.getLogger("uvicorn.error.cadence.seed")

# The well-known demo password is for LOCAL development only. Anywhere real,
# set CADENCE_SEED_PASSWORD (required when CADENCE_ENV=production); setting it also
# rotates the password of already-seeded staff accounts.
_DEV_PASSWORD = "cadence123"

# (name, email, role) — e-mails are the stable keys, so existing logins keep working.
_STAFF = [
    ("Sunita Verma", "receptionist@cadence.dev", Role.RECEPTIONIST),
    ("Rohan Kapoor", "nurse@cadence.dev", Role.TRIAGE_NURSE),
    ("Dr. Priya Sharma", "doctor@cadence.dev", Role.DOCTOR),
    ("Dr. Arjun Mehta", "doctor2@cadence.dev", Role.DOCTOR),
    ("Dr. Kavita Nair", "doctor3@cadence.dev", Role.DOCTOR),
    ("Vikram Singh", "admin@cadence.dev", Role.ADMINISTRATOR),
]

# doctor e-mail -> specialty (drives which appointment types / emergencies they take)
_DOCTORS = {
    "doctor@cadence.dev": "general",
    "doctor2@cadence.dev": "general",
    "doctor3@cadence.dev": "cardiology",
}

# Seeded shifts cover this many days ahead, so a long-lived demo never runs dry.
_SHIFT_DAYS = 14
# Clinic OPD hours in local time (IST): morning and afternoon sessions.
_SESSIONS = ((time(9, 0), time(13, 0)), (time(14, 0), time(18, 0)))

# (mrn, name, date of birth, sex, mobile, city, blood group, emergency contact, notes)
_PATIENTS = [
    ("CAD-100001", "Rajesh Kumar Verma", date(1978, 3, 14), "male", "+91 90000 10001",
     "New Delhi", "B+", "Sunita Verma (wife) · +91 90000 20001", "Type 2 diabetes; on metformin."),
    ("CAD-100002", "Ananya Iyer", date(1992, 9, 3), "female", "+91 90000 10002",
     "Bengaluru", "O+", "Venkat Iyer (father) · +91 90000 20002", None),
    ("CAD-100003", "Mohammed Irfan Qureshi", date(1985, 11, 21), "male", "+91 90000 10003",
     "Hyderabad", "A+", "Shabana Qureshi (wife) · +91 90000 20003", "Penicillin allergy."),
    ("CAD-100004", "Priyanka Chatterjee", date(1989, 6, 30), "female", "+91 90000 10004",
     "Kolkata", "AB+", "Subhash Chatterjee (husband) · +91 90000 20004", None),
    ("CAD-100005", "Harpreet Singh Gill", date(1971, 1, 8), "male", "+91 90000 10005",
     "Ludhiana", "B-", "Gurleen Kaur (wife) · +91 90000 20005", "Hypertension; on amlodipine."),
    ("CAD-100006", "Lakshmi Narayanan", date(1955, 12, 2), "female", "+91 90000 10006",
     "Chennai", "O+", "Ramesh Narayanan (son) · +91 90000 20006", "Known coronary artery disease."),
    ("CAD-100007", "Siddharth Deshmukh", date(2001, 4, 17), "male", "+91 90000 10007",
     "Pune", "A-", "Anita Deshmukh (mother) · +91 90000 20007", None),
    ("CAD-100008", "Fatima Sheikh", date(1996, 8, 25), "female", "+91 90000 10008",
     "Mumbai", "B+", "Imran Sheikh (brother) · +91 90000 20008", None),
    ("CAD-100009", "Devansh Patel", date(2015, 2, 11), "male", "+91 90000 10009",
     "Ahmedabad", "O+", "Hetal Patel (mother) · +91 90000 20009", "Asthma (mild)."),
    ("CAD-100010", "Kavya Reddy", date(1983, 7, 19), "female", "+91 90000 10010",
     "Vijayawada", "A+", "Suresh Reddy (husband) · +91 90000 20010", None),
]

# (name, default_duration_min, specialty)
_TYPES = [
    ("General OPD consultation", 30, "general"),
    ("Follow-up visit", 15, "general"),
    ("Extended consultation", 45, "general"),
    ("Cardiology consultation", 30, "cardiology"),
]
# Names used by earlier versions of this seed -> their new name (renamed in place so
# existing appointments keep pointing at the same row).
_TYPE_RENAMES = {
    "General consultation": "General OPD consultation",
    "Follow-up": "Follow-up visit",
}


def _ist_at(hour: int, minute: int = 0, *, plus_days: int = 0) -> datetime:
    """A wall-clock time in the clinic's timezone, on today + N days, as UTC."""
    tz = settings.clinic_tz
    local_day = datetime.now(tz).date() + timedelta(days=plus_days)
    return datetime.combine(local_day, time(hour, minute), tzinfo=tz).astimezone(UTC)


def _seed_password() -> str:
    if settings.seed_password:
        return settings.seed_password
    if settings.is_production:
        raise SystemExit(
            "Refusing to seed demo accounts in production without CADENCE_SEED_PASSWORD."
        )
    return _DEV_PASSWORD


def _ensure_staff(db: Session, password: str) -> None:
    for name, email, role in _STAFF:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(User(name=name, email=email, role=role, password_hash=hash_password(password)))
        else:
            user.name = name  # refresh display name from older seeds
            if settings.seed_password:
                user.password_hash = hash_password(password)


def _ensure_patients(db: Session) -> None:
    for mrn, name, dob, sex, mobile, city, blood, emergency, notes in _PATIENTS:
        patient = db.scalar(select(Patient).where(Patient.mrn == mrn))
        if patient is None:
            patient = Patient(mrn=mrn)
            db.add(patient)
        patient.name = name
        patient.date_of_birth = dob
        patient.sex = sex
        patient.contact = mobile
        patient.city = city
        patient.blood_group = blood
        patient.emergency_contact = emergency
        patient.notes = notes


def _ensure_types(db: Session) -> None:
    for old, new in _TYPE_RENAMES.items():
        old_row = db.scalar(select(AppointmentType).where(AppointmentType.name == old))
        if old_row is not None and (
            db.scalar(select(AppointmentType).where(AppointmentType.name == new)) is None
        ):
            old_row.name = new
    db.flush()
    for name, duration, specialty in _TYPES:
        row = db.scalar(select(AppointmentType).where(AppointmentType.name == name))
        if row is None:
            db.add(AppointmentType(name=name, default_duration_min=duration, specialty=specialty))
        else:
            row.default_duration_min = duration
            row.specialty = specialty


def _ensure_doctor_profiles_and_shifts(db: Session) -> None:
    tz = settings.clinic_tz
    midnight_utc = datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz).astimezone(UTC)
    wanted = {
        (_ist_at(s.hour, s.minute, plus_days=d), _ist_at(e.hour, e.minute, plus_days=d))
        for d in range(_SHIFT_DAYS)
        for s, e in _SESSIONS
    }
    for email, specialty in _DOCTORS.items():
        doctor = db.scalar(select(User).where(User.email == email))
        if doctor is None:
            continue
        profile = db.get(DoctorProfile, doctor.id)
        if profile is None:
            db.add(DoctorProfile(user_id=doctor.id, specialty=specialty))
        else:
            profile.specialty = specialty
        # Normalise this demo doctor's upcoming shifts to the IST sessions: drop the
        # old UTC-hour demo shifts so availability never overlaps or duplicates.
        existing = list(
            db.scalars(
                select(Shift).where(Shift.doctor_id == doctor.id, Shift.start_utc >= midnight_utc)
            )
        )
        have = {(s.start_utc, s.end_utc) for s in existing}
        stale = [s.id for s in existing if (s.start_utc, s.end_utc) not in wanted]
        if stale:
            db.execute(delete(Shift).where(Shift.id.in_(stale)))
        for start, end in sorted(wanted - have):
            db.add(Shift(doctor_id=doctor.id, start_utc=start, end_utc=end))


def _next_start(offset_min: int) -> datetime:
    """A start time for a *sample* appointment that is still in the future.

    Roughly now + ``offset_min`` rounded up to the quarter hour; if that falls
    outside OPD hours (before 9:30 am or after 5 pm clinic time) it rolls to 10:00
    the next morning, so the demo never opens on a schedule that is already hours
    behind.
    """
    tz = settings.clinic_tz
    local = datetime.now(tz) + timedelta(minutes=offset_min)
    local = local.replace(second=0, microsecond=0)
    local += timedelta(minutes=(-local.minute) % 15)
    if local.time() < time(9, 30) or local.time() > time(17, 0):
        day = local.date() + timedelta(days=0 if local.time() < time(9, 30) else 1)
        local = datetime.combine(day, time(10, 0), tzinfo=tz) + timedelta(minutes=offset_min % 90)
    return local.astimezone(UTC)


def _retire_past_demo_appointments(db: Session) -> None:
    """Demo patients' appointments that ended hours ago and were never actioned are
    history, not a live backlog: mark them completed so the dashboard starts clean."""
    cutoff = datetime.now(UTC) - timedelta(hours=2)
    mrns = [p[0] for p in _PATIENTS]
    ids = list(db.scalars(select(Patient.id).where(Patient.mrn.in_(mrns))))
    if not ids:
        return
    for appt in db.scalars(
        select(Appointment).where(
            Appointment.patient_id.in_(ids),
            Appointment.status.in_((AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN)),
            Appointment.scheduled_end < cutoff,
        )
    ):
        appt.status = AppointmentStatus.COMPLETED


def _ensure_sample_appointments(db: Session) -> None:
    def by_email(email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email))

    def by_type(name: str) -> AppointmentType | None:
        return db.scalar(select(AppointmentType).where(AppointmentType.name == name))

    def by_mrn(mrn: str) -> Patient | None:
        return db.scalar(select(Patient).where(Patient.mrn == mrn))

    _retire_past_demo_appointments(db)
    db.flush()
    now = datetime.now(UTC)
    # (doctor, patient MRN, type, minutes from now). Patients that already have an
    # upcoming appointment are skipped, so re-seeding never piles up duplicates.
    plan = [
        ("doctor@cadence.dev", "CAD-100001", "General OPD consultation", 45),
        ("doctor@cadence.dev", "CAD-100002", "Follow-up visit", 75),
        ("doctor@cadence.dev", "CAD-100003", "General OPD consultation", 105),
        ("doctor2@cadence.dev", "CAD-100005", "General OPD consultation", 60),
        ("doctor3@cadence.dev", "CAD-100006", "Cardiology consultation", 90),
    ]
    for email, mrn, type_name, offset in plan:
        doctor, patient, appt_type = by_email(email), by_mrn(mrn), by_type(type_name)
        if not (doctor and patient and appt_type):
            continue
        upcoming = db.scalar(
            select(Appointment.id).where(
                Appointment.patient_id == patient.id,
                Appointment.scheduled_start >= now,
                Appointment.status.in_((AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN)),
            )
        )
        if upcoming is not None:
            continue
        start = _next_start(offset)
        # A savepoint per row: an overlap with data someone created by hand is skipped,
        # not fatal (the database refuses overlapping active appointments).
        try:
            with db.begin_nested():
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
                db.flush()
        except IntegrityError:
            log.info("Skipped sample appointment %s for %s (slot already taken)", mrn, email)


def seed(*, quiet: bool = False) -> None:
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
        if quiet:
            return
        if settings.is_production or settings.seed_password:
            print("Seed complete (staff password taken from CADENCE_SEED_PASSWORD).")
        else:
            print(f"Seed complete. Development staff password: {_DEV_PASSWORD}")
    finally:
        db.close()


def refresh_demo_data() -> None:
    """Startup hook (``CADENCE_SEED_DEMO_ON_START``): never blocks the API from booting."""
    try:
        seed(quiet=True)
        log.info("Demo data refreshed.")
    except SystemExit as exc:
        log.warning("Demo data NOT refreshed: %s", exc)
    except Exception:  # noqa: BLE001 - a bad demo row must not take the API down
        log.exception("Demo data refresh failed; continuing without it")


if __name__ == "__main__":
    seed()
