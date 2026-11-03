"""Seed a realistic, synthetic Indian-hospital demo environment.

Run with ``python -m app.seed`` (after migrations), or set
``CADENCE_SEED_DEMO_ON_START=true`` for hosts without a shell. Seed records are
idempotent and keyed by stable demo identifiers (staff e-mail, patient MRN,
appointment patient/day, and decision idempotency key). Re-running never wipes
records created by staff and never duplicates the demo dataset.

All people, identifiers, telephone numbers, clinical examples and activity are
fictional. This is demonstration data, not patient information or clinical advice.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.enums import (
    Acuity,
    AppointmentOrigin,
    AppointmentStatus,
    AuditAction,
    Role,
)
from app.core.security import hash_password
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.audit import AuditLog
from app.models.decision import SchedulingDecision
from app.models.displacement import AppointmentDisplacement
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.triage import TriageAssessment
from app.models.user import User

log = logging.getLogger("uvicorn.error.cadence.seed")

# The well-known password is for LOCAL development only. Production must set
# CADENCE_SEED_PASSWORD; when set, it also rotates existing seeded staff passwords.
_DEV_PASSWORD = "cadence123"

# (name, email, role). E-mail is the stable key, so existing logins keep working.
_STAFF = [
    ("Sunita Verma", "receptionist@cadence.dev", Role.RECEPTIONIST),
    ("Neha Malhotra", "receptionist2@cadence.dev", Role.RECEPTIONIST),
    ("Rohan Kapoor", "nurse@cadence.dev", Role.TRIAGE_NURSE),
    ("Ayesha Khan", "nurse2@cadence.dev", Role.TRIAGE_NURSE),
    ("Dr. Priya Sharma", "doctor@cadence.dev", Role.DOCTOR),
    ("Dr. Arjun Mehta", "doctor2@cadence.dev", Role.DOCTOR),
    ("Dr. Kavita Nair", "doctor3@cadence.dev", Role.DOCTOR),
    ("Dr. Nikhil Bansal", "doctor4@cadence.dev", Role.DOCTOR),
    ("Dr. Meera Iyer", "doctor5@cadence.dev", Role.DOCTOR),
    ("Dr. Rahul Khanna", "doctor6@cadence.dev", Role.DOCTOR),
    ("Saurabh Raj Shekhar", "admin@cadence.dev", Role.ADMINISTRATOR),
]

# Doctor e-mail -> specialty (drives available appointment types and emergencies).
_DOCTORS = {
    "doctor@cadence.dev": "general",
    "doctor2@cadence.dev": "general",
    "doctor3@cadence.dev": "cardiology",
    "doctor4@cadence.dev": "pediatrics",
    "doctor5@cadence.dev": "orthopedics",
    "doctor6@cadence.dev": "dermatology",
}

# A 14-day schedule with morning and extended afternoon/evening OPD sessions.
_SHIFT_DAYS = 14
_SESSIONS = ((time(9, 0), time(13, 0)), (time(14, 0), time(22, 0)))

# (MRN, name, DOB, sex, mobile, city, blood group, emergency contact, notes)
_PATIENTS: list[tuple[str, str, date, str, str, str, str, str, str | None]] = [
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

# Additional fictional registrations give patient search/profile screens realistic depth.
_EXTRA_PATIENTS = [
    ("Aditi Malhotra", "1988-04-12", "female", "New Delhi", "O+", "Seasonal allergic rhinitis."),
    ("Vivek Sethi", "1976-01-29", "male", "New Delhi", "B+", "Routine blood pressure follow-up."),
    ("Nandini Rao", "1998-08-07", "female", "Bengaluru", "A+", None),
    ("Karan Chawla", "1990-12-18", "male", "New Delhi", "AB+", "History of lower back discomfort."),
    ("Mehul Shah", "1968-05-23", "male", "Ahmedabad", "O-", "Type 2 diabetes; routine review."),
    ("Ishita Bose", "2004-02-14", "female", "Kolkata", "B+", None),
    ("Armaan Siddiqui", "1982-07-02", "male", "Hyderabad", "A+", "Reports intermittent migraine."),
    ("Pooja Menon", "1994-10-26", "female", "Chennai", "O+", None),
    ("Ritesh Kulkarni", "1979-03-09", "male", "Pune", "B+", "Hypertension; routine follow-up."),
    ("Simran Kaur", "1991-06-15", "female", "Ludhiana", "A-", None),
    ("Aarav Bhatia", "2018-11-30", "male", "New Delhi", "O+", "Paediatric wellness visit."),
    ("Sneha Pillai", "1986-09-22", "female", "Kochi", "AB+", "Thyroid condition; monitored by physician."),
    ("Kabir Anand", "1995-01-17", "male", "Jaipur", "B+", None),
    ("Rhea Kapoor", "2000-05-05", "female", "Mumbai", "O+", None),
    ("Manoj Tiwari", "1962-12-01", "male", "Lucknow", "A+", "Age-related joint discomfort."),
    ("Tara Mukherjee", "1981-02-28", "female", "Kolkata", "B-", "Iron deficiency under routine monitoring."),
    ("Yash Agarwal", "1993-07-11", "male", "Jaipur", "AB+", None),
    ("Zoya Farooqui", "1987-10-04", "female", "Hyderabad", "O+", "Known dust allergy."),
    ("Varun Nambiar", "1973-04-19", "male", "Kochi", "B+", "Dyslipidaemia; routine review."),
    ("Divya Saxena", "1997-03-25", "female", "Bhopal", "A+", None),
    ("Aakash Joshi", "1984-06-08", "male", "Pune", "O-", "Sports-related knee discomfort."),
    ("Mitali Das", "1990-11-16", "female", "Kolkata", "B+", None),
    ("Farhan Ali", "1970-08-21", "male", "Hyderabad", "AB+", "Hypertension; on regular follow-up."),
    ("Kritika Sood", "2002-01-31", "female", "Chandigarh", "O+", None),
    ("Omkar Patil", "1989-09-12", "male", "Pune", "A+", "Recurrent shoulder discomfort."),
    ("Shreya Ghosh", "1996-04-06", "female", "Kolkata", "B+", None),
    ("Adil Hussain", "1980-02-17", "male", "Guwahati", "O+", "Seasonal respiratory symptoms."),
    ("Nisha Thomas", "1977-07-28", "female", "Kochi", "A-", "Routine cardiac risk review."),
    ("Devika Nair", "1999-12-10", "female", "Chennai", "AB+", None),
    ("Pranav Rao", "1985-05-14", "male", "Bengaluru", "B+", None),
    ("Maanvi Jain", "2012-03-03", "female", "Jaipur", "O+", "Paediatric follow-up."),
    ("Sameer Kulkarni", "1966-10-09", "male", "Pune", "A+", "Type 2 diabetes; routine review."),
    ("Tanvi Desai", "1992-01-20", "female", "Ahmedabad", "B+", None),
    ("Gaurav Mishra", "1974-09-01", "male", "Lucknow", "O+", "Hypertension; follow-up advised."),
    ("Esha Roy", "1988-12-13", "female", "Kolkata", "AB-", None),
    ("Rohit Choudhary", "1998-06-27", "male", "Jaipur", "A+", None),
    ("Nupur Arora", "1983-03-31", "female", "Chandigarh", "O+", "Migraine history."),
    ("Harish Menon", "1959-08-16", "male", "Chennai", "B+", "Cardiac history; routine monitoring."),
    ("Iqra Khan", "2005-07-24", "female", "Hyderabad", "A-", None),
    ("Neil D'Souza", "1991-02-05", "male", "Mumbai", "O+", None),
    ("Aniket Joshi", "1972-11-11", "male", "Pune", "AB+", "Routine orthopaedic follow-up."),
    ("Sana Mirza", "1995-04-28", "female", "New Delhi", "B+", None),
    ("Raghav Bedi", "1986-10-02", "male", "Chandigarh", "O-", "Dermatology follow-up."),
    ("Maya Krishnan", "1964-01-06", "female", "Chennai", "A+", "Osteoarthritis; mobility review."),
    ("Rehan Qazi", "2003-05-18", "male", "Lucknow", "B+", None),
    ("Jhanvi Mehta", "1994-08-30", "female", "Ahmedabad", "O+", None),
    ("Suresh Babu", "1957-06-03", "male", "Bengaluru", "A+", "Routine chronic-care review."),
    ("Ayesha Dutta", "1989-12-22", "female", "Guwahati", "AB+", None),
    ("Rohan Batra", "1978-02-09", "male", "New Delhi", "B-", "Blood pressure follow-up."),
    ("Ira Fernandes", "2010-09-14", "female", "Mumbai", "O+", "Paediatric wellness review."),
    ("Amrita Basu", "1982-05-19", "female", "Kolkata", "A+", "Cardiac risk review."),
    ("Vikram Rao", "1975-11-07", "male", "Bengaluru", "B+", "Routine specialist follow-up."),
    ("Leena Bhat", "1993-09-16", "female", "Pune", "O-", "No known chronic conditions recorded."),
    ("Manav Suri", "1987-03-22", "male", "New Delhi", "AB+", "Routine outpatient review."),
]

for _index, (_name, _dob, _sex, _city, _blood, _notes) in enumerate(_EXTRA_PATIENTS, start=11):
    _PATIENTS.append((
        f"CAD-100{_index:03d}", _name, date.fromisoformat(_dob), _sex,
        f"+91 90000 {10000 + _index:05d}", _city, _blood,
        f"Demo family contact {_index} · +91 90000 {20000 + _index:05d}", _notes,
    ))

_TYPES = [
    ("General OPD consultation", 30, "general"),
    ("Follow-up visit", 15, "general"),
    ("Extended consultation", 45, "general"),
    ("Cardiology consultation", 30, "cardiology"),
    ("Pediatric consultation", 30, "pediatrics"),
    ("Orthopedic consultation", 45, "orthopedics"),
    ("Dermatology consultation", 30, "dermatology"),
]
_TYPE_RENAMES = {
    "General consultation": "General OPD consultation",
    "Follow-up": "Follow-up visit",
}


def _ist_at(day: date, clock: time) -> datetime:
    """Convert a clinic wall-clock time into UTC."""
    return datetime.combine(day, clock, tzinfo=settings.clinic_tz).astimezone(UTC)


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
            user.name = name
            user.role = role
            user.is_active = True
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
        if old_row is not None and db.scalar(
            select(AppointmentType).where(AppointmentType.name == new)
        ) is None:
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
    today = datetime.now(tz).date()
    midnight_utc = _ist_at(today, time.min)
    wanted = {
        (_ist_at(today + timedelta(days=day), start), _ist_at(today + timedelta(days=day), end))
        for day in range(_SHIFT_DAYS)
        for start, end in _SESSIONS
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
        existing = list(db.scalars(
            select(Shift).where(Shift.doctor_id == doctor.id, Shift.start_utc >= midnight_utc)
        ))
        have = {(shift.start_utc, shift.end_utc) for shift in existing}
        stale = [shift.id for shift in existing if (shift.start_utc, shift.end_utc) not in wanted]
        if stale:
            db.execute(delete(Shift).where(Shift.id.in_(stale)))
        for start, end in sorted(wanted - have):
            db.add(Shift(doctor_id=doctor.id, start_utc=start, end_utc=end))


def _add_audit_once(
    db: Session,
    *,
    entity_type: str,
    entity_id: int | str,
    action: AuditAction,
    actor_id: int | None,
    reason: str,
    before: dict | None = None,
    after: dict | None = None,
    created_at: datetime | None = None,
) -> None:
    found = db.scalar(select(AuditLog.id).where(
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == str(entity_id),
        AuditLog.reason == reason,
    ))
    if found is None:
        db.add(AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action.value,
            actor_id=actor_id,
            before=before,
            after=after,
            reason=reason,
            created_at=created_at or datetime.now(UTC),
        ))


def _appointment_status(start: datetime, end: datetime, now: datetime) -> AppointmentStatus:
    if end <= now:
        return AppointmentStatus.COMPLETED
    if start <= now < end:
        return AppointmentStatus.IN_PROGRESS
    if start > now and start <= now + timedelta(minutes=25):
        return AppointmentStatus.CHECKED_IN
    return AppointmentStatus.BOOKED


def _normalise_clinic_start(candidate: datetime, duration_min: int) -> datetime:
    """Keep demo appointments out of the 13:00–14:00 lunch closure."""
    day = candidate.date()
    tz = settings.clinic_tz
    lunch_start = datetime.combine(day, time(13, 0), tzinfo=tz)
    lunch_end = datetime.combine(day, time(14, 0), tzinfo=tz)
    end = candidate + timedelta(minutes=duration_min)
    if lunch_start <= candidate < lunch_end or candidate < lunch_start < end:
        return lunch_end
    return candidate


def _live_anchor(now: datetime) -> datetime:
    local = now.astimezone(settings.clinic_tz)
    rounded = local.replace(minute=(local.minute // 15) * 15, second=0, microsecond=0)
    candidate = rounded - timedelta(minutes=15)
    opening = datetime.combine(local.date(), time(9, 0), tzinfo=settings.clinic_tz)
    candidate = max(candidate, opening + timedelta(hours=2, minutes=30))
    if time(13, 0) <= candidate.time() < time(14, 0):
        candidate = datetime.combine(local.date(), time(14, 0), tzinfo=settings.clinic_tz)
    closing_anchor = datetime.combine(local.date(), time(20, 30), tzinfo=settings.clinic_tz)
    candidate = min(candidate, closing_anchor)
    return _normalise_clinic_start(candidate, 30)


def _type_for_specialty(types: dict[str, AppointmentType], specialty: str, index: int) -> AppointmentType:
    if index % 3 == 1:
        return types["Follow-up visit"]
    if specialty == "cardiology":
        return types["Cardiology consultation"]
    if specialty == "pediatrics":
        return types["Pediatric consultation"]
    if specialty == "orthopedics":
        return types["Orthopedic consultation"]
    if specialty == "dermatology":
        return types["Dermatology consultation"]
    return types["Extended consultation"] if index % 3 == 2 else types["General OPD consultation"]


def _patient_has_appointment_today(db: Session, patient_id: int, lo: datetime, hi: datetime) -> bool:
    return db.scalar(select(Appointment.id).where(
        Appointment.patient_id == patient_id,
        Appointment.scheduled_start >= lo,
        Appointment.scheduled_start < hi,
        Appointment.status != AppointmentStatus.CANCELLED,
    )) is not None


def _ensure_sample_appointments(db: Session) -> None:
    """Build a populated, clock-aware schedule without overwriting user activity."""
    now = datetime.now(UTC)
    local_now = now.astimezone(settings.clinic_tz)
    day = local_now.date()
    day_start, day_end = _ist_at(day, time.min), _ist_at(day + timedelta(days=1), time.min)
    patients = {p.mrn: p for p in db.scalars(select(Patient).where(
        Patient.mrn.in_([row[0] for row in _PATIENTS])
    ))}
    doctors = {u.email: u for u in db.scalars(select(User).where(
        User.email.in_(list(_DOCTORS) + ["receptionist@cadence.dev"])
    ))}
    types = {t.name: t for t in db.scalars(select(AppointmentType))}
    _retire_past_demo_appointments(db)
    db.flush()

    live_start = _live_anchor(now)
    history_slots = [
        (time(9, 0), "General OPD consultation", Acuity.A5),
        (time(9, 35), "Follow-up visit", Acuity.A4),
        (time(10, 0), "Extended consultation", Acuity.A5),
        (time(10, 50), "Follow-up visit", Acuity.A5),
    ]
    future_acuities = [Acuity.A2, Acuity.A3, Acuity.A4]
    current_types = {
        "general": "General OPD consultation",
        "cardiology": "Cardiology consultation",
        "pediatrics": "Pediatric consultation",
        "orthopedics": "Orthopedic consultation",
        "dermatology": "Dermatology consultation",
    }

    for doctor_index, (email, specialty) in enumerate(_DOCTORS.items()):
        doctor = doctors.get(email)
        if doctor is None:
            continue
        case_mrns = [f"CAD-{100001 + doctor_index * 10 + index:06d}" for index in range(10)]
        doctor_slots: list[tuple[Patient, AppointmentType, datetime, Acuity, AppointmentOrigin]] = []

        # Four early appointments provide a visible same-day completion/no-show history.
        for index, (clock, type_name, acuity) in enumerate(history_slots):
            mrn = case_mrns[index]
            patient = patients.get(mrn)
            appt_type = types.get(type_name)
            if patient is None or appt_type is None:
                continue
            local_start = datetime.combine(day, clock, tzinfo=settings.clinic_tz)
            local_start = _normalise_clinic_start(local_start, appt_type.default_duration_min)
            start = local_start.astimezone(UTC)
            end = start + timedelta(minutes=appt_type.default_duration_min)
            status = _appointment_status(start, end, now)
            # The fourth early slot is a realistic no-show example once it has passed.
            if index == 3 and end < now - timedelta(minutes=30):
                status = AppointmentStatus.NO_SHOW
            doctor_slots.append((patient, appt_type, start, acuity, AppointmentOrigin.BOOKED))
            if _patient_has_appointment_today(db, patient.id, day_start, day_end):
                continue
            try:
                with db.begin_nested():
                    appt = Appointment(
                        patient_id=patient.id,
                        doctor_id=doctor.id,
                        type_id=appt_type.id,
                        scheduled_start=start,
                        scheduled_end=end,
                        status=status,
                        origin=AppointmentOrigin.BOOKED,
                        acuity=acuity,
                        version=1,
                    )
                    db.add(appt)
                    db.flush()
                    _add_audit_once(
                        db, entity_type="appointment", entity_id=appt.id,
                        action=AuditAction.CREATE, actor_id=doctors.get("receptionist@cadence.dev", doctor).id,
                        reason="Demo seed: appointment registered",
                        after={"patient_id": patient.id, "doctor_id": doctor.id,
                               "status": status.value, "scheduled_start": start.isoformat()},
                        created_at=min(now, start - timedelta(minutes=20)),
                    )
                    if status != AppointmentStatus.BOOKED:
                        _add_audit_once(
                            db, entity_type="appointment", entity_id=appt.id,
                            action=AuditAction.UPDATE, actor_id=doctor.id,
                            reason=f"Demo seed: {status.value} workflow scenario",
                            before={"status": AppointmentStatus.BOOKED.value},
                            after={"status": status.value}, created_at=min(now, end),
                        )
            except IntegrityError:
                log.info("Skipped demo appointment for %s; a live schedule conflict exists", mrn)

        # One currently-running consult (during clinic hours) followed by a real queue.
        for index in range(4, 8):
            mrn = case_mrns[index]
            patient = patients.get(mrn)
            if patient is None:
                continue
            appt_type = (
                types[current_types[specialty]] if index == 4
                else _type_for_specialty(types, specialty, index)
            )
            if index == 4:
                local_start = live_start
                acuity = Acuity.A3 if doctor_index % 2 == 0 else Acuity.A4
            else:
                previous_end = (doctor_slots[-1][2] + timedelta(
                    minutes=doctor_slots[-1][1].default_duration_min
                )) if doctor_slots else live_start + timedelta(minutes=30)
                local_previous_end = previous_end.astimezone(settings.clinic_tz)
                candidate = local_previous_end + timedelta(minutes=5)
                local_start = _normalise_clinic_start(candidate, appt_type.default_duration_min)
                acuity = future_acuities[index - 5]
            start = local_start.astimezone(UTC)
            end = start + timedelta(minutes=appt_type.default_duration_min)
            status = _appointment_status(start, end, now)
            doctor_slots.append((patient, appt_type, start, acuity, AppointmentOrigin.BOOKED))
            if end.astimezone(settings.clinic_tz).time() > time(22, 0):
                continue
            if _patient_has_appointment_today(db, patient.id, day_start, day_end):
                continue
            try:
                with db.begin_nested():
                    appt = Appointment(
                        patient_id=patient.id,
                        doctor_id=doctor.id,
                        type_id=appt_type.id,
                        scheduled_start=start,
                        scheduled_end=end,
                        status=status,
                        origin=AppointmentOrigin.BOOKED,
                        acuity=acuity,
                        version=1,
                    )
                    db.add(appt)
                    db.flush()
                    actor = doctors.get("receptionist@cadence.dev")
                    _add_audit_once(
                        db, entity_type="appointment", entity_id=appt.id,
                        action=AuditAction.CREATE, actor_id=actor.id if actor else None,
                        reason="Demo seed: appointment registered",
                        after={"patient_id": patient.id, "doctor_id": doctor.id,
                               "status": status.value, "scheduled_start": start.isoformat()},
                        created_at=min(now, start - timedelta(minutes=20)),
                    )
                    if status != AppointmentStatus.BOOKED:
                        _add_audit_once(
                            db, entity_type="appointment", entity_id=appt.id,
                            action=AuditAction.UPDATE, actor_id=doctor.id,
                            reason=f"Demo seed: {status.value} workflow scenario",
                            before={"status": AppointmentStatus.BOOKED.value},
                            after={"status": status.value}, created_at=min(now, end),
                        )
            except IntegrityError:
                log.info("Skipped demo appointment for %s; a live schedule conflict exists", mrn)


def _ensure_future_appointments(db: Session) -> None:
    """Keep the next six days populated so the date navigator is useful too."""
    today = datetime.now(settings.clinic_tz).date()
    demo_mrns = [row[0] for row in _PATIENTS]
    patients = {p.mrn: p for p in db.scalars(select(Patient).where(Patient.mrn.in_(demo_mrns)))}
    doctors = {u.email: u for u in db.scalars(select(User).where(User.email.in_(list(_DOCTORS))))}
    types = {t.name: t for t in db.scalars(select(AppointmentType))}
    actor = db.scalar(select(User).where(User.email == "receptionist@cadence.dev"))

    for day_offset in range(1, 7):
        day = today + timedelta(days=day_offset)
        day_start, day_end = _ist_at(day, time.min), _ist_at(day + timedelta(days=1), time.min)
        for doctor_index, (email, specialty) in enumerate(_DOCTORS.items()):
            doctor = doctors.get(email)
            if doctor is None:
                continue
            # Rotate through each doctor's synthetic patient panel rather than
            # booking the same people on every future date.
            panel_start = doctor_index * 10
            patient_indexes = ((day_offset * 2) % 10, (day_offset * 2 + 1) % 10)
            for slot_index, (clock, patient_offset) in enumerate(
                zip((time(10, 0), time(15, 0)), patient_indexes, strict=True)
            ):
                mrn = f"CAD-{100001 + panel_start + patient_offset:06d}"
                patient = patients.get(mrn)
                if patient is None or _patient_has_appointment_today(
                    db, patient.id, day_start, day_end
                ):
                    continue
                appt_type = _type_for_specialty(types, specialty, slot_index)
                local_start = datetime.combine(day, clock, tzinfo=settings.clinic_tz)
                local_start = _normalise_clinic_start(local_start, appt_type.default_duration_min)
                start = local_start.astimezone(UTC)
                end = start + timedelta(minutes=appt_type.default_duration_min)
                try:
                    with db.begin_nested():
                        appt = Appointment(
                            patient_id=patient.id, doctor_id=doctor.id, type_id=appt_type.id,
                            scheduled_start=start, scheduled_end=end,
                            status=AppointmentStatus.BOOKED, origin=AppointmentOrigin.BOOKED,
                            acuity=Acuity.A5 if slot_index else Acuity.A4, version=1,
                        )
                        db.add(appt)
                        db.flush()
                        _add_audit_once(
                            db, entity_type="appointment", entity_id=appt.id,
                            action=AuditAction.CREATE, actor_id=actor.id if actor else None,
                            reason="Demo seed: future appointment booked",
                            after={"patient_id": patient.id, "doctor_id": doctor.id,
                                   "status": AppointmentStatus.BOOKED.value,
                                   "scheduled_start": start.isoformat()},
                            created_at=datetime.now(UTC),
                        )
                except IntegrityError:
                    log.info("Skipped future demo slot for %s; a schedule conflict exists", mrn)


def _retire_past_demo_appointments(db: Session) -> None:
    """Turn stale, unactioned demo bookings into completed history."""
    cutoff = datetime.now(UTC) - timedelta(hours=2)
    mrns = [row[0] for row in _PATIENTS]
    ids = list(db.scalars(select(Patient.id).where(Patient.mrn.in_(mrns))))
    if not ids:
        return
    for appt in db.scalars(select(Appointment).where(
        Appointment.patient_id.in_(ids),
        Appointment.status.in_((AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN,
                                 AppointmentStatus.IN_PROGRESS)),
        Appointment.scheduled_end < cutoff,
    )):
        appt.status = AppointmentStatus.COMPLETED


def _ensure_triage_scenarios(db: Session) -> None:
    now = datetime.now(UTC)
    patients = {p.mrn: p for p in db.scalars(select(Patient).where(
        Patient.mrn.in_([row[0] for row in _PATIENTS])
    ))}
    nurse = db.scalar(select(User).where(User.email == "nurse@cadence.dev"))
    if nurse is None:
        return
    scenarios = [
        ("CAD-100049", Acuity.A2, "Shortness of breath during exertion",
         {"blood_pressure": "146/92", "heart_rate_bpm": 108, "temperature_c": 37.1,
          "oxygen_saturation_pct": 95}),
        ("CAD-100050", Acuity.A3, "Persistent abdominal discomfort",
         {"blood_pressure": "128/82", "heart_rate_bpm": 92, "temperature_c": 37.0,
          "oxygen_saturation_pct": 98}),
        ("CAD-100051", Acuity.A4, "Headache with light sensitivity",
         {"blood_pressure": "122/80", "heart_rate_bpm": 78, "temperature_c": 36.8}),
        ("CAD-100052", Acuity.A5, "Seasonal allergy symptoms",
         {"blood_pressure": "118/76", "heart_rate_bpm": 72, "temperature_c": 36.7}),
        ("CAD-100053", Acuity.A3, "Wrist pain following a minor fall",
         {"blood_pressure": "124/80", "heart_rate_bpm": 84, "temperature_c": 36.9}),
        ("CAD-100054", Acuity.A2, "Palpitations and light-headedness",
         {"blood_pressure": "142/88", "heart_rate_bpm": 112, "temperature_c": 36.9}),
        ("CAD-100063", Acuity.A1, "Severe chest discomfort; clinician review requested",
         {"blood_pressure": "92/60", "heart_rate_bpm": 126, "temperature_c": 37.2,
          "oxygen_saturation_pct": 93}),
        ("CAD-100061", Acuity.A2, "Chest tightness with palpitations; urgent review",
         {"blood_pressure": "138/86", "heart_rate_bpm": 116, "temperature_c": 37.0,
          "oxygen_saturation_pct": 96}),
        ("CAD-100064", Acuity.A3, "Acute knee pain; assessment requested",
         {"blood_pressure": "126/82", "heart_rate_bpm": 88, "temperature_c": 36.8}),
    ]
    for index, (mrn, acuity, complaint, vitals) in enumerate(scenarios):
        patient = patients.get(mrn)
        if patient is None:
            continue
        exists = db.scalar(select(TriageAssessment.id).where(
            TriageAssessment.patient_id == patient.id,
            TriageAssessment.chief_complaint == complaint,
        ))
        if exists is not None:
            continue
        assessed_at = now - timedelta(minutes=8 + index * 4)
        consumed_at = now if mrn in {"CAD-100049", "CAD-100061"} else None
        assessment = TriageAssessment(
            patient_id=patient.id,
            nurse_id=nurse.id,
            acuity=acuity,
            chief_complaint=complaint,
            vitals=vitals,
            assessed_at=assessed_at,
            consumed_at=consumed_at,
        )
        db.add(assessment)
        db.flush()
        _add_audit_once(
            db, entity_type="triage", entity_id=assessment.id,
            action=AuditAction.CREATE, actor_id=nurse.id,
            reason="Demo seed: triage assessment recorded",
            after={"patient_id": patient.id, "acuity": acuity.value,
                   "chief_complaint": complaint},
            created_at=assessed_at,
        )


def _decision_key(kind: str, day: date) -> str:
    return f"cadence-demo-{kind}-{day.isoformat()}"


def _ensure_decision_scenarios(db: Session) -> None:
    now = datetime.now(UTC)
    local_day = now.astimezone(settings.clinic_tz).date()
    patients = {p.mrn: p for p in db.scalars(select(Patient).where(
        Patient.mrn.in_([row[0] for row in _PATIENTS])
    ))}
    doctors = {u.email: u for u in db.scalars(select(User).where(
        User.email.in_(list(_DOCTORS) + ["nurse@cadence.dev", "admin@cadence.dev"])
    ))}
    types = {t.name: t for t in db.scalars(select(AppointmentType))}
    nurse, admin = doctors.get("nurse@cadence.dev"), doctors.get("admin@cadence.dev")
    cardiologist = doctors.get("doctor3@cadence.dev")
    emergency_patient, displaced_patient = patients.get("CAD-100061"), patients.get("CAD-100062")
    cardiology_type = types.get("Cardiology consultation")

    # An auto-committed emergency and a 30-minute displacement for the trace screen.
    auto_key = _decision_key("auto", local_day)
    auto = db.scalar(select(SchedulingDecision).where(
        SchedulingDecision.idempotency_key == auto_key
    ))
    if auto is None and all((nurse, cardiologist, emergency_patient, displaced_patient,
                            cardiology_type)):
        # Find a real 60-minute gap in the cardiologist's evening shift. The
        # inserted emergency occupies the first half; the displaced routine
        # booking is moved into the adjacent second half.
        clinic_now = now.astimezone(settings.clinic_tz)
        first_candidate = clinic_now.replace(second=0, microsecond=0)
        minute = ((first_candidate.minute + 14) // 15) * 15
        first_candidate = first_candidate.replace(minute=0) + timedelta(minutes=minute)
        first_candidate = max(
            first_candidate,
            datetime.combine(local_day, time(14, 0), tzinfo=settings.clinic_tz),
        )
        last_candidate = datetime.combine(local_day, time(21, 0), tzinfo=settings.clinic_tz)
        cardiologist_busy = list(db.scalars(select(Appointment).where(
            Appointment.doctor_id == cardiologist.id,
            Appointment.status.in_((AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN,
                                    AppointmentStatus.IN_PROGRESS)),
            Appointment.scheduled_start < _ist_at(local_day + timedelta(days=1), time.min),
            Appointment.scheduled_end > _ist_at(local_day, time.min),
        )))
        emergency_start = None
        candidate = first_candidate
        while candidate <= last_candidate:
            candidate_utc = candidate.astimezone(UTC)
            window_end = candidate_utc + timedelta(minutes=60)
            if not any(
                item.scheduled_start < window_end and item.scheduled_end > candidate_utc
                for item in cardiologist_busy
            ):
                emergency_start = candidate_utc
                break
            candidate += timedelta(minutes=15)
        moved_start = emergency_start + timedelta(minutes=30) if emergency_start else None
        emergency = db.scalar(select(Appointment).where(
            Appointment.patient_id == emergency_patient.id,
            Appointment.scheduled_start >= _ist_at(local_day, time.min),
            Appointment.scheduled_start < _ist_at(local_day + timedelta(days=1), time.min),
        ))
        moved = db.scalar(select(Appointment).where(
            Appointment.patient_id == displaced_patient.id,
            Appointment.scheduled_start >= _ist_at(local_day, time.min),
            Appointment.scheduled_start < _ist_at(local_day + timedelta(days=1), time.min),
        ))
        if emergency_start is not None and emergency is None and moved is None:
            try:
                with db.begin_nested():
                    emergency = Appointment(
                        patient_id=emergency_patient.id,
                        doctor_id=cardiologist.id,
                        type_id=cardiology_type.id,
                        scheduled_start=emergency_start,
                        scheduled_end=emergency_start + timedelta(minutes=30),
                        status=_appointment_status(emergency_start,
                                                   emergency_start + timedelta(minutes=30), now),
                        origin=AppointmentOrigin.EMERGENCY,
                        acuity=Acuity.A2,
                        version=1,
                    )
                    moved = Appointment(
                        patient_id=displaced_patient.id,
                        doctor_id=cardiologist.id,
                        type_id=cardiology_type.id,
                        scheduled_start=moved_start,
                        scheduled_end=moved_start + timedelta(minutes=30),
                        status=_appointment_status(moved_start, moved_start + timedelta(minutes=30), now),
                        origin=AppointmentOrigin.BOOKED,
                        acuity=Acuity.A5,
                        displacement_count=1,
                        version=2,
                    )
                    db.add_all([emergency, moved])
                    db.flush()
                    auto = SchedulingDecision(
                        trigger="emergency_insert",
                        status="auto_committed",
                        engine_version="cadence-demo-1.0",
                        actor_id=nurse.id,
                        patient_id=emergency_patient.id,
                        emergency_appointment_id=emergency.id,
                        idempotency_key=auto_key,
                        request_hash=hashlib.sha256(auto_key.encode()).hexdigest(),
                        input_snapshot={"patient_id": emergency_patient.id,
                                        "acuity": Acuity.A2.value,
                                        "type_id": cardiology_type.id,
                                        "demo_record": True},
                        chosen_plan={"placement": {"doctor_id": cardiologist.id,
                                                    "start": emergency_start.isoformat(),
                                                    "end": (emergency_start + timedelta(minutes=30)).isoformat()},
                                       "moves": [{"appointment_id": moved.id,
                                                  "from_start": emergency_start.isoformat(),
                                                  "to_start": moved_start.isoformat(),
                                                  "delay_min": 30}]},
                        alternatives=[{"placement": {"doctor_id": cardiologist.id,
                                                       "start": emergency_start.isoformat(),
                                                       "end": (emergency_start + timedelta(minutes=30)).isoformat()},
                                       "moves": [{"appointment_id": moved.id,
                                                  "from_start": emergency_start.isoformat(),
                                                  "to_start": moved_start.isoformat()}]}],
                        parameters={"max_displacements": 2, "max_auto_displaced": 1,
                                    "max_auto_delay_min": 30},
                        reasons=["priority_a2_emergency_insertion"],
                        created_at=now - timedelta(minutes=18),
                    )
                    db.add(auto)
                    db.flush()
                    db.add(AppointmentDisplacement(
                        appointment_id=moved.id,
                        decision_id=auto.id,
                        from_start=emergency_start,
                        to_start=moved_start,
                        reason="A2 emergency priority insertion",
                        created_at=now - timedelta(minutes=18),
                    ))
                    _add_audit_once(
                        db, entity_type="scheduling_decision", entity_id=auto.id,
                        action=AuditAction.CREATE, actor_id=nurse.id,
                        reason="Demo seed: emergency insertion auto-committed",
                        after={"patient_id": emergency_patient.id,
                               "emergency_appointment_id": emergency.id},
                        created_at=now - timedelta(minutes=18),
                    )
            except IntegrityError:
                log.info("Skipped demonstration emergency displacement; schedule is occupied")

    # An A1 scenario deliberately remains pending: the app's policy requires human direction.
    escalation_key = _decision_key("escalation", local_day)
    pending = db.scalar(select(SchedulingDecision).where(
        SchedulingDecision.idempotency_key == escalation_key
    ))
    critical_patient = patients.get("CAD-100063")
    if pending is None and nurse is not None and critical_patient is not None:
        pending = SchedulingDecision(
            trigger="emergency_insert",
            status="escalated",
            engine_version="cadence-demo-1.0",
            actor_id=nurse.id,
            patient_id=critical_patient.id,
            emergency_appointment_id=None,
            idempotency_key=escalation_key,
            request_hash=hashlib.sha256(escalation_key.encode()).hexdigest(),
            input_snapshot={"patient_id": critical_patient.id,
                            "acuity": Acuity.A1.value,
                            "demo_record": True},
            chosen_plan=None,
            alternatives=[{"status": "manual_review", "label": "Clinician-directed placement"}],
            parameters={"max_displacements": 2, "max_auto_displaced": 1,
                        "max_auto_delay_min": 30},
            reasons=["acuity_a1_human_directed"],
            created_at=now - timedelta(minutes=9),
        )
        db.add(pending)
        db.flush()
        _add_audit_once(
            db, entity_type="scheduling_decision", entity_id=pending.id,
            action=AuditAction.CREATE, actor_id=nurse.id,
            reason="Demo seed: A1 escalation awaits clinician review",
            after={"patient_id": critical_patient.id, "status": "escalated"},
            created_at=now - timedelta(minutes=9),
        )

    # A resolved historical escalation demonstrates the governance workflow too.
    resolved_key = _decision_key("resolved", local_day)
    resolved = db.scalar(select(SchedulingDecision).where(
        SchedulingDecision.idempotency_key == resolved_key
    ))
    resolved_patient = patients.get("CAD-100064")
    if resolved is None and nurse is not None and admin is not None and resolved_patient is not None:
        resolved = SchedulingDecision(
            trigger="emergency_insert",
            status="escalated",
            engine_version="cadence-demo-1.0",
            actor_id=nurse.id,
            patient_id=resolved_patient.id,
            emergency_appointment_id=None,
            idempotency_key=resolved_key,
            request_hash=hashlib.sha256(resolved_key.encode()).hexdigest(),
            input_snapshot={"patient_id": resolved_patient.id,
                            "acuity": Acuity.A3.value,
                            "demo_record": True},
            chosen_plan=None,
            alternatives=[{"status": "clinician_reviewed", "label": "Next available specialist"}],
            parameters={"max_displacements": 2, "max_auto_displaced": 1,
                        "max_auto_delay_min": 30},
            reasons=["no_feasible_plan"],
            created_at=now - timedelta(hours=2),
            resolved_at=now - timedelta(hours=1, minutes=40),
            resolved_by=admin.id,
            resolution_note="Clinician reviewed the options and arranged an appropriate follow-up.",
        )
        db.add(resolved)
        db.flush()
        _add_audit_once(
            db, entity_type="scheduling_decision", entity_id=resolved.id,
            action=AuditAction.RESOLVE, actor_id=admin.id,
            reason="Demo seed: historical escalation resolved by administrator",
            after={"resolved_at": resolved.resolved_at.isoformat(),
                   "resolution_note": resolved.resolution_note},
            created_at=resolved.resolved_at,
        )


def _ensure_patient_audit_history(db: Session) -> None:
    actor = db.scalar(select(User).where(User.email == "receptionist@cadence.dev"))
    if actor is None:
        return
    for mrn, name, *_ in _PATIENTS:
        patient = db.scalar(select(Patient).where(Patient.mrn == mrn))
        if patient is not None:
            _add_audit_once(
                db, entity_type="patient", entity_id=patient.id,
                action=AuditAction.CREATE, actor_id=actor.id,
                reason="Demo seed: patient registration",
                after={"mrn": patient.mrn, "name": name},
                created_at=patient.created_at if hasattr(patient, "created_at") else None,
            )


def seed(*, quiet: bool = False) -> None:
    password = _seed_password()
    db = SessionLocal()
    try:
        _ensure_staff(db, password)
        _ensure_patients(db)
        _ensure_types(db)
        db.flush()
        _ensure_doctor_profiles_and_shifts(db)
        db.flush()
        _ensure_sample_appointments(db)
        _ensure_future_appointments(db)
        _ensure_triage_scenarios(db)
        _ensure_decision_scenarios(db)
        _ensure_patient_audit_history(db)
        db.commit()
        if quiet:
            return
        print("Synthetic Cadence demo data refreshed (patients, staff, schedule, triage and audit).")
        if settings.is_production or settings.seed_password:
            print("Seeded staff passwords are taken from CADENCE_SEED_PASSWORD.")
        else:
            print(f"Development staff password: {_DEV_PASSWORD}")
    finally:
        db.close()


def refresh_demo_data() -> None:
    """Startup hook: refresh demo data without preventing the API from booting."""
    try:
        seed(quiet=True)
        log.info("Synthetic demo data refreshed.")
    except SystemExit as exc:
        log.warning("Demo data NOT refreshed: %s", exc)
    except Exception:  # noqa: BLE001 - a bad demo row must not take the API down
        log.exception("Demo data refresh failed; continuing without it")


if __name__ == "__main__":
    seed()
