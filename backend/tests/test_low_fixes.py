"""Regression tests for the low-severity issues found in the audit."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import mongomock
import pytest
import time_machine
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import settings
from app.core.db import Base
from app.core.enums import Acuity, AppointmentStatus, Role
from app.core.mongo import set_mongo_override
from app.main import app
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.scheduling.availability import Interval
from app.scheduling.engine import EngineAppointment, EngineRequest, EngineState, insert_emergency

T = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)
BACKEND = Path(__file__).resolve().parent.parent


def hour(h: int, m: int = 0) -> datetime:
    return T.replace(hour=h, minute=m)


# --- 16. a no-show is history, not something to rewrite as "cancelled" ---


def test_a_no_show_appointment_cannot_be_cancelled(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = user_factory(Role.DOCTOR, email="d@x.dev")
        db_session.add(DoctorProfile(user_id=doctor.id, specialty="general"))
        appt_type = AppointmentType(name="Consult", default_duration_min=30, specialty="general")
        patient = Patient(mrn="CAD-L00001", name="Late Lata", date_of_birth=date(1990, 1, 1),
                          sex="female")
        db_session.add_all([appt_type, patient])
        db_session.commit()
        appt = Appointment(patient_id=patient.id, doctor_id=doctor.id, type_id=appt_type.id,
                           scheduled_start=hour(12), scheduled_end=hour(12, 30),
                           status=AppointmentStatus.NO_SHOW, acuity=Acuity.A5)
        db_session.add(appt)
        db_session.commit()
        resp = client.post(f"/appointments/{appt.id}/cancel", json={},
                           headers=auth_headers(user_factory(Role.RECEPTIONIST)))
        assert resp.status_code == 409


# --- 17. displaced patients can move to the next shift, across the lunch break ---


def test_the_ripple_can_continue_into_the_afternoon_shift() -> None:
    morning, afternoon = Interval(hour(9), hour(13)), Interval(hour(14), hour(18))
    booked = EngineAppointment(1, 1, 10, hour(12, 30), hour(13), AppointmentStatus.BOOKED)
    decision = insert_emergency(
        EngineState({1: (morning, afternoon)}, (booked,)),
        EngineRequest(99, Acuity.A2, 30, (1,), hour(12, 30)),
    )
    plans = ([decision.chosen] if decision.chosen else []) + list(decision.alternatives)
    usable = [p for p in plans if p.feasible and p.moves]
    assert usable, "the 12:30 patient should be movable to the afternoon shift"
    assert usable[0].moves[0].to_start == hour(14)
    assert decision.status == "escalate"  # a 90-minute delay is a human decision


def test_a_single_shift_still_overflows_when_there_is_nowhere_to_go() -> None:
    only = Interval(hour(9), hour(13))
    booked = EngineAppointment(1, 1, 10, hour(12, 30), hour(13), AppointmentStatus.BOOKED)
    decision = insert_emergency(
        EngineState({1: (only,)}, (booked,)),
        EngineRequest(99, Acuity.A2, 30, (1,), hour(12, 30)),
    )
    plans = ([decision.chosen] if decision.chosen else []) + list(decision.alternatives)
    assert not any(p.feasible and p.moves for p in plans)


# --- 18. a routine arrival is never offered a plan that displaces booked patients ---


def test_a_routine_arrival_is_never_offered_a_displacing_plan() -> None:
    shift = Interval(hour(9), hour(10))  # fully booked, so any placement would displace someone
    booked = (
        EngineAppointment(1, 1, 10, hour(9), hour(9, 30), AppointmentStatus.BOOKED),
        EngineAppointment(2, 1, 11, hour(9, 30), hour(10), AppointmentStatus.BOOKED),
    )
    decision = insert_emergency(
        EngineState({1: (shift,)}, booked), EngineRequest(99, Acuity.A5, 30, (1,), hour(9))
    )
    plans = ([decision.chosen] if decision.chosen else []) + list(decision.alternatives)
    assert all(not p.moves for p in plans)
    assert decision.status == "escalate" and "no_feasible_plan" in decision.reasons


# --- 19. a crash answers in JSON, like every other error ---


def test_an_unhandled_error_returns_the_json_error_envelope(
    client: TestClient, user_factory: Any, auth_headers: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = auth_headers(user_factory(Role.ADMINISTRATOR))

    def explode(*_: Any, **__: Any) -> None:
        raise RuntimeError("boom: internal detail that must not leak")

    monkeypatch.setattr("app.api.patients.search_patients", explode)
    crashing = TestClient(app, raise_server_exceptions=False)
    resp = crashing.get("/patients", headers=headers)
    assert resp.status_code == 500
    error = resp.json()["error"]
    assert error["code"] == "internal_error"
    assert "boom" not in resp.text  # no internals in the response


# --- MRN allocation survives a collision ---


def test_registration_retries_when_a_generated_mrn_is_taken(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session.add(Patient(mrn="CAD-111111", name="Existing", date_of_birth=date(1980, 1, 1),
                           sex="male"))
    db_session.commit()
    candidates = iter(["CAD-111111", "CAD-222222"])
    monkeypatch.setattr("app.services.patients._generate_mrn", lambda: next(candidates))
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    resp = client.post("/patients", headers=headers,
                       json={"name": "Asha Rao", "date_of_birth": "1990-01-01", "sex": "female"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["mrn"] == "CAD-222222"


def test_registration_gives_up_cleanly_if_every_mrn_collides(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_session.add(Patient(mrn="CAD-333333", name="Existing", date_of_birth=date(1980, 1, 1),
                           sex="male"))
    db_session.commit()
    monkeypatch.setattr("app.services.patients._generate_mrn", lambda: "CAD-333333")
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    resp = client.post("/patients", headers=headers,
                       json={"name": "Asha Rao", "date_of_birth": "1990-01-01", "sex": "female"})
    assert resp.status_code == 409


# --- clinical details are not sent to the front desk ---


def test_the_medical_block_is_withheld_from_the_front_desk(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    patient = Patient(mrn="CAD-L00002", name="Private Pat", date_of_birth=date(1970, 1, 1),
                      sex="male")
    db_session.add(patient)
    db_session.commit()
    set_mongo_override(mongomock.MongoClient().low_fix)
    try:
        nurse = auth_headers(user_factory(Role.TRIAGE_NURSE))
        saved = client.put(f"/patients/{patient.id}/profile", headers=nurse, json={
            "medical": {"conditions": ["Diabetes"],
                        "allergies": [{"substance": "Penicillin", "severity": "severe"}]}})
        assert saved.status_code == 200
        assert saved.json()["profile"]["medical"]["conditions"] == ["Diabetes"]
        admin = auth_headers(user_factory(Role.ADMINISTRATOR, email="boss@x.dev"))
        assert client.put(f"/patients/{patient.id}/profile", headers=admin,
                          json={"address": {"city": "Pune"}}).status_code == 200

        for role, email in ((Role.DOCTOR, "d@x.dev"), (Role.ADMINISTRATOR, "a@x.dev")):
            seen = client.get(f"/patients/{patient.id}/profile",
                              headers=auth_headers(user_factory(role, email=email))).json()
            assert seen["profile"]["medical"]["conditions"] == ["Diabetes"]
            assert seen["redacted"] == []

        desk = client.get(f"/patients/{patient.id}/profile",
                          headers=auth_headers(user_factory(Role.RECEPTIONIST))).json()
        assert "medical" not in desk["profile"] and desk["redacted"] == ["medical"]
        assert desk["profile"]["address"]["city"] == "Pune"  # everything else is still visible
        assert "Diabetes" not in str(desk) and "Penicillin" not in str(desk)
    finally:
        set_mongo_override(None)


# --- the UI learns the clinic timezone from the server ---


def test_the_public_config_exposes_the_clinic_timezone(client: TestClient) -> None:
    resp = client.get("/config")
    assert resp.status_code == 200
    assert resp.json() == {"clinic_timezone": settings.clinic_timezone}


# --- migrations and models describe the same schema ---


def test_running_every_migration_produces_exactly_the_models_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'drift.db'}"
    monkeypatch.setattr(settings, "database_url", url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(config, "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        drift = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert drift == [], f"models and migrations disagree: {drift}"
