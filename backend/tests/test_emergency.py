"""Emergency flow tests: triage, dry-run plan, commit, idempotency, escalation."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Acuity, AppointmentOrigin, Role
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.triage import TriageAssessment
from app.models.user import User


def _aligned_now() -> datetime:
    """Current UTC rounded up to the next 15-minute grid point.

    The clinic scenarios are anchored here (not a fixed hour) for two reasons:
    the engine's response-time windows are measured from ``now``, and commit now
    rejects a plan whose ``now`` is >10 min behind the wall clock — both break if
    ``now`` is a fixed time of day. Grid alignment matches the engine's anchor
    stepping so an emergency lands exactly on a booked slot when it must displace.
    """
    now = datetime.now(UTC)
    base = now.replace(minute=0, second=0, microsecond=0)
    steps = math.ceil((now - base).total_seconds() / 60.0 / 15 - 1e-9)
    return base + timedelta(minutes=steps * 15)


# One stable reference time for the whole module (the suite runs in seconds, so
# this stays well inside the 10-minute plan-expiry window).
_NOW = _aligned_now()


def _rel(minutes: int) -> datetime:
    return _NOW + timedelta(minutes=minutes)


def _mk_doctor(db: Session, user_factory: Callable[..., User], email: str) -> User:
    doctor = user_factory(Role.DOCTOR, email=email)
    db.add(DoctorProfile(user_id=doctor.id, specialty="general"))
    return doctor


def _mk_patient(db: Session, mrn: str, name: str) -> Patient:
    p = Patient(mrn=mrn, name=name, date_of_birth=date(1990, 1, 1), sex="other")
    db.add(p)
    db.flush()
    return p


def _triage(db: Session, patient_id: int, acuity: str, *, nurse_id: int | None = None) -> None:
    """Record a triage so the server will authorize plan/commit for this patient.

    ``assessed_at`` defaults to real ``utcnow`` and the server's validity check is
    a 12-hour lower bound, so a freshly-written row is always in-window.
    """
    db.add(
        TriageAssessment(
            patient_id=patient_id,
            nurse_id=nurse_id if nurse_id is not None else patient_id,
            acuity=Acuity(acuity),
            chief_complaint="chest pain",
        )
    )
    db.commit()


@pytest.fixture()
def setup_open(db_session: Session, user_factory: Callable[..., User]) -> dict[str, int]:
    """A doctor with an open 3-hour shift spanning ``now``, a 30-min type, one patient."""
    doctor = _mk_doctor(db_session, user_factory, "edoc@cadence.dev")
    db_session.add(Shift(doctor_id=doctor.id, start_utc=_rel(0), end_utc=_rel(180)))
    appt_type = AppointmentType(name="General", default_duration_min=30, specialty="general")
    db_session.add(appt_type)
    patient = _mk_patient(db_session, "CAD-E0001", "Emergency Patient")
    db_session.commit()
    return {"doctor_id": doctor.id, "type_id": appt_type.id, "patient_id": patient.id}


def _plan_body(setup: dict[str, int], acuity: str) -> dict[str, object]:
    return {
        "patient_id": setup["patient_id"],
        "type_id": setup["type_id"],
        "acuity": acuity,
        "now": _NOW.isoformat(),
    }


# --- triage ------------------------------------------------------------------


def test_nurse_can_record_triage(
    client: TestClient,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    nurse = user_factory(Role.TRIAGE_NURSE)
    resp = client.post(
        "/triage",
        headers=auth_headers(nurse),
        json={
            "patient_id": setup_open["patient_id"],
            "acuity": "a2",
            "chief_complaint": "chest pain",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["acuity"] == "a2"


def test_receptionist_cannot_record_triage(
    client: TestClient,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    recep = user_factory(Role.RECEPTIONIST)
    resp = client.post(
        "/triage",
        headers=auth_headers(recep),
        json={"patient_id": setup_open["patient_id"], "acuity": "a2", "chief_complaint": "x"},
    )
    assert resp.status_code == 403


# --- plan (dry-run) ----------------------------------------------------------


def test_plan_is_dry_run_and_does_not_mutate(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    nurse = user_factory(Role.TRIAGE_NURSE)
    _triage(db_session, setup_open["patient_id"], "a3")
    resp = client.post(
        "/emergencies/plan", headers=auth_headers(nurse), json=_plan_body(setup_open, "a3")
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"]["status"] == "auto"
    assert body["fingerprint"]
    assert body["now"]  # plan echoes the instant it was computed against (A4)
    # No appointment was created by the dry-run.
    assert db_session.scalar(select(Appointment).limit(1)) is None


# --- commit ------------------------------------------------------------------


def test_commit_applies_emergency(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, setup_open["patient_id"], "a3")
    plan = client.post(
        "/emergencies/plan", headers=headers, json=_plan_body(setup_open, "a3")
    ).json()

    body = _plan_body(setup_open, "a3")
    body["fingerprint"] = plan["fingerprint"]
    resp = client.post("/emergencies/commit", headers=headers, json=body)
    assert resp.status_code == 200
    assert resp.json()["status"] == "auto"
    assert resp.json()["emergency_appointment_id"] is not None

    appt = db_session.scalar(select(Appointment))
    assert appt is not None
    assert appt.origin == AppointmentOrigin.EMERGENCY


def test_commit_is_idempotent(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, setup_open["patient_id"], "a3")
    plan = client.post(
        "/emergencies/plan", headers=headers, json=_plan_body(setup_open, "a3")
    ).json()

    body = _plan_body(setup_open, "a3")
    body["fingerprint"] = plan["fingerprint"]
    body["idempotency_key"] = "emg-key-123"

    first = client.post("/emergencies/commit", headers=headers, json=body).json()
    second = client.post("/emergencies/commit", headers=headers, json=body).json()
    assert first["decision_id"] == second["decision_id"]
    # Exactly one emergency appointment exists.
    assert len(list(db_session.scalars(select(Appointment)))) == 1


def test_commit_rejects_stale_fingerprint(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, setup_open["patient_id"], "a3")
    body = _plan_body(setup_open, "a3")
    body["fingerprint"] = "not-the-real-fingerprint"
    resp = client.post("/emergencies/commit", headers=headers, json=body)
    assert resp.status_code == 409
    assert resp.json()["error"]["details"]["code"] == "schedule_changed"


# --- escalation --------------------------------------------------------------


def test_a1_plan_escalates(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, setup_open["patient_id"], "a1")
    resp = client.post("/emergencies/plan", headers=headers, json=_plan_body(setup_open, "a1"))
    assert resp.status_code == 200
    assert resp.json()["decision"]["status"] == "escalate"
    assert resp.json()["decision"]["chosen"] is None


def test_a1_commit_does_not_auto_apply(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, setup_open["patient_id"], "a1")
    plan = client.post(
        "/emergencies/plan", headers=headers, json=_plan_body(setup_open, "a1")
    ).json()
    body = _plan_body(setup_open, "a1")
    body["fingerprint"] = plan["fingerprint"]
    resp = client.post("/emergencies/commit", headers=headers, json=body)
    assert resp.status_code == 200
    assert resp.json()["status"] == "escalate"
    assert resp.json()["emergency_appointment_id"] is None
    # No appointment was created.
    assert db_session.scalar(select(Appointment).limit(1)) is None


# --- displacement ------------------------------------------------------------


def test_emergency_displaces_a_booked_appointment(
    client: TestClient,
    db_session: Session,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    # Shift spanning now (1h), one booked appt at now (30m); an A2 must displace it.
    doctor = _mk_doctor(db_session, user_factory, "ddoc@cadence.dev")
    db_session.add(Shift(doctor_id=doctor.id, start_utc=_rel(0), end_utc=_rel(60)))
    appt_type = AppointmentType(name="General", default_duration_min=30, specialty="general")
    booked_patient = _mk_patient(db_session, "CAD-B0001", "Booked Patient")
    emerg_patient = _mk_patient(db_session, "CAD-B0002", "Walk-in Patient")
    db_session.add(appt_type)
    db_session.flush()
    booked = Appointment(
        patient_id=booked_patient.id,
        doctor_id=doctor.id,
        type_id=appt_type.id,
        scheduled_start=_rel(0),
        scheduled_end=_rel(30),
        version=1,
    )
    db_session.add(booked)
    db_session.commit()
    booked_id = booked.id

    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    setup = {"patient_id": emerg_patient.id, "type_id": appt_type.id}
    _triage(db_session, emerg_patient.id, "a2")
    plan = client.post("/emergencies/plan", headers=headers, json=_plan_body(setup, "a2")).json()
    assert plan["decision"]["status"] == "auto"
    assert plan["decision"]["chosen"]["moves"], "a full in-window shift must force a displacement"

    body = _plan_body(setup, "a2")
    body["fingerprint"] = plan["fingerprint"]
    resp = client.post("/emergencies/commit", headers=headers, json=body).json()
    assert resp["status"] == "auto"
    assert any(d["appointment_id"] == booked_id for d in resp["displaced"])

    db_session.expire_all()
    moved = db_session.get(Appointment, booked_id)
    assert moved is not None
    assert moved.displacement_count == 1
    assert moved.scheduled_start == _rel(30)


# --- acuity enforcement (A2) -------------------------------------------------


def test_plan_requires_a_recent_triage(
    client: TestClient,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    # No triage recorded for this patient.
    resp = client.post("/emergencies/plan", headers=headers, json=_plan_body(setup_open, "a3"))
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["code"] == "triage_required"


def test_plan_rejects_acuity_mismatch(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, setup_open["patient_id"], "a3")  # nurse recorded A3
    resp = client.post(
        "/emergencies/plan", headers=headers, json=_plan_body(setup_open, "a2")
    )  # requested A2
    assert resp.status_code == 422
    body = resp.json()["error"]
    assert body["details"]["code"] == "acuity_mismatch"
    assert body["details"]["recorded_acuity"] == "a3"


def test_commit_requires_matching_triage(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, setup_open["patient_id"], "a3")
    plan = client.post(
        "/emergencies/plan", headers=headers, json=_plan_body(setup_open, "a3")
    ).json()
    # Commit asking for a different acuity than was triaged.
    body = _plan_body(setup_open, "a2")
    body["fingerprint"] = plan["fingerprint"]
    resp = client.post("/emergencies/commit", headers=headers, json=body)
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["code"] == "acuity_mismatch"


def test_latest_triage_endpoint_reflects_recorded_acuity(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    pid = setup_open["patient_id"]
    # Nothing recorded yet → null (receptionist sees "a nurse must triage first").
    empty = client.get(f"/patients/{pid}/latest-triage", headers=recep)
    assert empty.status_code == 200
    assert empty.json() is None

    _triage(db_session, pid, "a2")
    got = client.get(f"/patients/{pid}/latest-triage", headers=recep)
    assert got.status_code == 200
    assert got.json()["acuity"] == "a2"


# --- plan freshness (A4) -----------------------------------------------------


def test_commit_rejects_an_expired_plan(
    client: TestClient,
    db_session: Session,
    setup_open: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, setup_open["patient_id"], "a3")
    plan = client.post(
        "/emergencies/plan", headers=headers, json=_plan_body(setup_open, "a3")
    ).json()
    # Echo a plan "now" from 20 minutes ago — past the 10-minute freshness window.
    body = _plan_body(setup_open, "a3")
    body["now"] = (datetime.now(UTC) - timedelta(minutes=20)).isoformat()
    body["fingerprint"] = plan["fingerprint"]
    resp = client.post("/emergencies/commit", headers=headers, json=body)
    assert resp.status_code == 409
    assert resp.json()["error"]["details"]["code"] == "plan_expired"
