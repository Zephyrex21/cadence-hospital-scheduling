"""Consultation status + queue API tests, incl. end-to-end in-progress protection."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Acuity, AppointmentStatus, Role
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.triage import TriageAssessment
from app.models.user import User


def _aligned_now() -> datetime:
    """Current UTC rounded up to the next 15-minute grid point (see test_emergency)."""
    now = datetime.now(UTC)
    base = now.replace(minute=0, second=0, microsecond=0)
    steps = math.ceil((now - base).total_seconds() / 60.0 / 15 - 1e-9)
    return base + timedelta(minutes=steps * 15)


_NOW = _aligned_now()


def _rel(minutes: int) -> datetime:
    return _NOW + timedelta(minutes=minutes)


@pytest.fixture()
def setup(db_session: Session, user_factory: Callable[..., User]) -> dict[str, int]:
    doctor = user_factory(Role.DOCTOR, email="cdoc@cadence.dev")
    db_session.add(DoctorProfile(user_id=doctor.id, specialty="general"))
    db_session.add(Shift(doctor_id=doctor.id, start_utc=_rel(0), end_utc=_rel(180)))
    appt_type = AppointmentType(name="General", default_duration_min=30, specialty="general")
    patient = _mk_patient(db_session, "CAD-C0001", "Queued Patient")
    emerg = _mk_patient(db_session, "CAD-C0002", "Walk-in Patient")
    db_session.add(appt_type)
    db_session.flush()
    booked = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        type_id=appt_type.id,
        scheduled_start=_rel(0),
        scheduled_end=_rel(30),
        version=1,
    )
    db_session.add(booked)
    db_session.commit()
    return {
        "doctor_id": doctor.id,
        "type_id": appt_type.id,
        "patient_id": patient.id,
        "emerg_patient_id": emerg.id,
        "appt_id": booked.id,
    }


def _mk_patient(db: Session, mrn: str, name: str) -> Patient:
    p = Patient(mrn=mrn, name=name, date_of_birth=date(1990, 1, 1), sex="other")
    db.add(p)
    db.flush()
    return p


def _status(client, headers, appt_id, action):  # type: ignore[no-untyped-def]
    return client.post(f"/appointments/{appt_id}/status", headers=headers, json={"action": action})


# --- transitions -------------------------------------------------------------


def test_doctor_can_walk_an_appointment_through_consultation(
    client: TestClient,
    setup: dict[str, int],
    db_session: Session,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    doctor = db_session.get(User, setup["doctor_id"])
    assert doctor is not None
    headers = auth_headers(doctor)

    assert _status(client, headers, setup["appt_id"], "check_in").json()["status"] == "checked_in"
    assert _status(client, headers, setup["appt_id"], "start").json()["status"] == "in_progress"
    assert _status(client, headers, setup["appt_id"], "complete").json()["status"] == "completed"


def test_invalid_transition_is_rejected(
    client: TestClient,
    setup: dict[str, int],
    db_session: Session,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    doctor = db_session.get(User, setup["doctor_id"])
    assert doctor is not None
    # Cannot complete an appointment that is still booked.
    resp = _status(client, auth_headers(doctor), setup["appt_id"], "complete")
    assert resp.status_code == 409
    assert resp.json()["error"]["details"]["code"] == "invalid_transition"


def test_other_doctor_cannot_change_appointment(
    client: TestClient,
    setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    other = user_factory(Role.DOCTOR, email="otherdoc@cadence.dev")
    resp = _status(client, auth_headers(other), setup["appt_id"], "check_in")
    assert resp.status_code == 403


def test_receptionist_cannot_change_status(
    client: TestClient,
    setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    recep = user_factory(Role.RECEPTIONIST)
    resp = _status(client, auth_headers(recep), setup["appt_id"], "check_in")
    assert resp.status_code == 403


# --- queue -------------------------------------------------------------------


def test_queue_lists_waiting_patient_with_estimate(
    client: TestClient,
    setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    resp = client.get("/queue", headers=headers, params={"now": _NOW.isoformat()})
    assert resp.status_code == 200
    entries = resp.json()
    assert any(e["appointment_id"] == setup["appt_id"] for e in entries)
    entry = next(e for e in entries if e["appointment_id"] == setup["appt_id"])
    assert entry["est_wait_min"] == 0  # first in an otherwise empty queue
    assert entry["patient"]["mrn"] == "CAD-C0001"


# --- end-to-end: in-progress is never displaced ------------------------------


def test_in_progress_consultation_is_never_displaced_by_emergency(
    client: TestClient,
    setup: dict[str, int],
    db_session: Session,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    doctor = db_session.get(User, setup["doctor_id"])
    assert doctor is not None
    # Start the booked consultation (now protected).
    _status(client, auth_headers(doctor), setup["appt_id"], "start")

    nurse_headers = auth_headers_for(db_session, auth_headers)
    # Triage the walk-in (A3) so the server authorizes scheduling it.
    db_session.add(
        TriageAssessment(
            patient_id=setup["emerg_patient_id"],
            nurse_id=setup["doctor_id"],
            acuity=Acuity.A3,
            chief_complaint="abdominal pain",
        )
    )
    db_session.commit()
    plan_body = {
        "patient_id": setup["emerg_patient_id"],
        "type_id": setup["type_id"],
        "acuity": "a3",
        "now": _NOW.isoformat(),
    }
    plan = client.post("/emergencies/plan", headers=nurse_headers, json=plan_body).json()
    assert plan["decision"]["status"] == "auto"
    chosen = plan["decision"]["chosen"]
    assert all(m["appointment_id"] != setup["appt_id"] for m in chosen["moves"])

    commit_body = {**plan_body, "fingerprint": plan["fingerprint"]}
    resp = client.post("/emergencies/commit", headers=nurse_headers, json=commit_body).json()
    assert resp["status"] == "auto"
    assert all(d["appointment_id"] != setup["appt_id"] for d in resp["displaced"])

    db_session.expire_all()
    protected = db_session.get(Appointment, setup["appt_id"])
    assert protected is not None
    assert protected.status == AppointmentStatus.IN_PROGRESS


def auth_headers_for(
    db: Session, auth_headers: Callable[[User], dict[str, str]]
) -> dict[str, str]:
    """A triage-nurse auth header (the role allowed to run the emergency flow)."""
    nurse = User(
        name="Nurse",
        email="qnurse@cadence.dev",
        role=Role.TRIAGE_NURSE,
        password_hash="x",
        is_active=True,
    )
    db.add(nurse)
    db.commit()
    db.refresh(nurse)
    return auth_headers(nurse)
