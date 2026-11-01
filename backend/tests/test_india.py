"""Indian-clinic behaviour: IST "today", richer patient records, Indian demo data."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import clinic_day_bounds
from app.core.config import settings
from app.core.enums import AppointmentOrigin, AppointmentStatus, Role
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.user import User

IST = "Asia/Kolkata"


# --- IST day boundaries -----------------------------------------------------------------
def test_clinic_day_starts_at_midnight_ist() -> None:
    settings.clinic_timezone = IST
    # 01:30 IST on 31 Oct is still 30 Oct in UTC — the clinic day must be the IST one.
    lo, hi = clinic_day_bounds(datetime(2026, 10, 30, 20, 0, tzinfo=UTC))
    assert lo == datetime(2026, 10, 30, 18, 30, tzinfo=UTC)
    assert hi == datetime(2026, 10, 31, 18, 30, tzinfo=UTC)
    # Noon UTC (what the frontend sends for a picked date) is 17:30 IST: same IST date.
    lo2, _ = clinic_day_bounds(datetime(2026, 10, 31, 12, 0, tzinfo=UTC))
    assert lo2 == datetime(2026, 10, 30, 18, 30, tzinfo=UTC)


def test_schedule_lists_the_ist_day_not_the_utc_day(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    settings.clinic_timezone = IST
    doc = user_factory(Role.DOCTOR, email="ist-doc@x.dev")
    db_session.add(DoctorProfile(user_id=doc.id, specialty="general"))
    t = AppointmentType(name="G", default_duration_min=30, specialty="general")
    p = Patient(mrn="CAD-IST1", name="Asha Rao", date_of_birth=date(1990, 1, 1), sex="female")
    db_session.add_all([t, p])
    db_session.flush()
    # 00:30 IST on 31 Oct == 19:00 UTC on 30 Oct.
    start = datetime(2026, 10, 30, 19, 0, tzinfo=UTC)
    db_session.add(
        Appointment(
            patient_id=p.id, doctor_id=doc.id, type_id=t.id, scheduled_start=start,
            scheduled_end=start + timedelta(minutes=30), status=AppointmentStatus.BOOKED,
            origin=AppointmentOrigin.BOOKED, version=1,
        )
    )
    db_session.commit()
    h = auth_headers(user_factory(Role.RECEPTIONIST))
    on_31 = client.get("/schedule", headers=h, params={"day": "2026-10-31T12:00:00Z"}).json()
    on_30 = client.get("/schedule", headers=h, params={"day": "2026-10-30T12:00:00Z"}).json()
    assert [a["patient"]["name"] for a in on_31] == ["Asha Rao"]
    assert on_30 == []


# --- richer patient records ----------------------------------------------------------------
def test_patient_can_be_registered_with_any_detail_and_found_by_city_or_phone(
    client: TestClient, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    h = auth_headers(user_factory(Role.RECEPTIONIST))
    body = {
        "name": "  सीमा शर्मा  ",  # any unicode name, surrounding spaces trimmed
        "date_of_birth": "1988-02-29",
        "sex": "female",
        "contact": "+91 98765 43210",
        "city": "Jaipur",
        "blood_group": "O-",
        "emergency_contact": "Ravi Sharma (husband) · +91 98765 00000",
        "notes": "Allergic to sulfa drugs.",
    }
    res = client.post("/patients", json=body, headers=h)
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["name"] == "सीमा शर्मा" and created["city"] == "Jaipur"
    assert created["blood_group"] == "O-" and created["notes"] == "Allergic to sulfa drugs."
    for q in ("Jaipur", "98765", "शर्मा", created["mrn"]):
        found = client.get("/patients", params={"q": q}, headers=h).json()
        assert [p["id"] for p in found] == [created["id"]], q
    # Everything but name / DOB / sex stays optional; blanks are stored as null.
    minimal = client.post(
        "/patients",
        json={"name": "Om", "date_of_birth": "2000-01-01", "sex": "other", "city": "  "},
        headers=h,
    ).json()
    assert minimal["city"] is None and minimal["contact"] is None


# --- Indian demo data ----------------------------------------------------------------------
@pytest.fixture()
def seed_module(db_session: Session, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    import app.seed as seed_mod

    monkeypatch.setattr(
        seed_mod, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    )
    monkeypatch.setattr(settings, "seed_password", None)
    monkeypatch.setattr(settings, "env", "development")
    settings.clinic_timezone = IST
    return seed_mod


def test_seed_upgrades_old_placeholder_data_in_place(
    db_session: Session, seed_module  # type: ignore[no-untyped-def]
) -> None:
    from app.core.security import hash_password

    # What an older deployment has: placeholder names, an old type name, UTC-hour shifts.
    doc = User(name="Dr. Amara Osei", email="doctor@cadence.dev", role=Role.DOCTOR,
               password_hash=hash_password("x"))
    old_patient = Patient(mrn="CAD-100001", name="John Carter", date_of_birth=date(1980, 4, 12),
                          sex="male", contact="555-0101")
    mine = Patient(mrn="CAD-777777", name="Registered By Hand", date_of_birth=date(1999, 9, 9),
                   sex="other")
    old_type = AppointmentType(name="General consultation", default_duration_min=30,
                               specialty="general")
    db_session.add_all([doc, old_patient, mine, old_type])
    db_session.flush()
    type_id, today = old_type.id, datetime.now(UTC)
    db_session.add(Shift(doctor_id=doc.id, start_utc=today.replace(hour=9, minute=0),
                         end_utc=today.replace(hour=12, minute=0)))
    db_session.commit()

    seed_module.seed(quiet=True)
    db_session.expire_all()

    assert db_session.scalar(select(User.name).where(User.email == "doctor@cadence.dev")) == (
        "Dr. Priya Sharma"
    )
    p1 = db_session.scalar(select(Patient).where(Patient.mrn == "CAD-100001"))
    assert p1 is not None and p1.name == "Rajesh Kumar Verma" and p1.contact.startswith("+91")
    assert p1.city == "New Delhi" and p1.blood_group == "B+"
    renamed = db_session.get(AppointmentType, type_id)  # same row, new name
    assert renamed is not None and renamed.name == "General OPD consultation"
    assert db_session.scalar(select(Patient.name).where(Patient.mrn == "CAD-777777")) == (
        "Registered By Hand"
    )
    # Shifts are IST sessions (09:00-13:00 / 14:00-18:00 IST) for every demo doctor, 14 days.
    assert db_session.scalar(select(func.count()).select_from(Shift)) == 3 * 14 * 2
    first = db_session.scalars(select(Shift).order_by(Shift.start_utc)).first()
    assert first is not None and first.start_utc.astimezone(settings.clinic_tz).hour in (9, 14)
    assert db_session.scalar(select(func.count()).select_from(Appointment)) >= 4


def test_seed_is_idempotent(db_session: Session, seed_module) -> None:  # type: ignore[no-untyped-def]
    seed_module.seed(quiet=True)
    tables = (User, Patient, Shift, Appointment)

    def counts() -> list[int | None]:
        return [db_session.scalar(select(func.count()).select_from(m)) for m in tables]

    seed_module.seed(quiet=True)
    before = counts()
    seed_module.seed(quiet=True)
    db_session.expire_all()
    assert counts() == before


def test_demo_refresh_never_blocks_startup_in_production_without_password(
    seed_module, monkeypatch: pytest.MonkeyPatch  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "seed_password", None)
    seed_module.refresh_demo_data()  # logs a warning, does not raise


def test_app_startup_refreshes_demo_data_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.seed as seed_mod
    from app.main import create_app

    calls: list[int] = []
    monkeypatch.setattr(seed_mod, "refresh_demo_data", lambda: calls.append(1))
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(settings, "seed_demo_on_start", False)
    with TestClient(create_app()):
        pass
    assert calls == []
    monkeypatch.setattr(settings, "seed_demo_on_start", True)
    with TestClient(create_app()):
        pass
    assert calls == [1]
