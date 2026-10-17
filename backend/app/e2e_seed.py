"""Deterministic, now-relative seed for the Playwright signature-flow E2E.

Creates exactly the state the end-to-end test drives:

* an administrator to sign in as (can do every step of the flow);
* a *cardiology* doctor with a wide-open shift — the booking step targets them,
  and because they are not ``general`` they are never eligible for the walk-in;
* a *general* doctor whose one-hour shift holds a single booked appointment, so a
  30-minute A2 walk-in is forced to displace it.

All data is synthetic and exists only for the E2E.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.enums import AppointmentOrigin, AppointmentStatus, Role
from app.core.security import hash_password
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.base import utcnow
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.user import User


def _align_up(dt: datetime, step_min: int = 15) -> datetime:
    base = dt.replace(minute=0, second=0, microsecond=0)
    minutes = (dt - base).total_seconds() / 60.0
    steps = math.ceil(minutes / step_min - 1e-9)
    return base + timedelta(minutes=steps * step_min)


def seed_e2e() -> None:
    db: Session = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == "admin@cadence.dev")) is not None:
            return  # already seeded

        pw = hash_password("cadence123")
        admin = User(
            name="Admin User", email="admin@cadence.dev", role=Role.ADMINISTRATOR,
            password_hash=pw, is_active=True,
        )
        able = User(
            name="Dr. Able Cardio", email="able@cadence.dev", role=Role.DOCTOR,
            password_hash=pw, is_active=True,
        )
        baker = User(
            name="Dr. Baker General", email="baker@cadence.dev", role=Role.DOCTOR,
            password_hash=pw, is_active=True,
        )
        db.add_all([admin, able, baker])
        db.flush()

        db.add(DoctorProfile(user_id=able.id, specialty="cardiology"))
        db.add(DoctorProfile(user_id=baker.id, specialty="general"))

        general = AppointmentType(
            name="General consultation", default_duration_min=30, specialty="general"
        )
        db.add(general)

        booked_patient = Patient(
            mrn="CAD-E0001", name="Booked Barbara", date_of_birth=date(1980, 1, 1), sex="female"
        )
        spare = Patient(
            mrn="CAD-E0002", name="Spare Sam", date_of_birth=date(1975, 3, 3), sex="male"
        )
        walkin = Patient(
            mrn="CAD-E0003", name="Walkin Wendy", date_of_birth=date(1990, 5, 5), sex="female"
        )
        db.add_all([booked_patient, spare, walkin])
        db.flush()

        now = utcnow()
        t0 = _align_up(now)
        # Able: an open cardiology shift spanning "now", for the booking step.
        db.add(
            Shift(
                doctor_id=able.id,
                start_utc=now - timedelta(minutes=30),
                end_utc=now + timedelta(hours=4),
            )
        )
        # Baker: a one-hour general shift holding a single booked appointment, so a
        # 30-minute A2 walk-in must displace it rather than slot in cleanly.
        db.add(Shift(doctor_id=baker.id, start_utc=t0, end_utc=t0 + timedelta(minutes=60)))
        db.add(
            Appointment(
                patient_id=booked_patient.id,
                doctor_id=baker.id,
                type_id=general.id,
                scheduled_start=t0,
                scheduled_end=t0 + timedelta(minutes=30),
                status=AppointmentStatus.BOOKED,
                origin=AppointmentOrigin.BOOKED,
                version=1,
            )
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_e2e()
