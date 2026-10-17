"""History/reporting tests: displacements, decision trace, audit, and RBAC."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Acuity, Role
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.triage import TriageAssessment
from app.models.user import User
from app.services.emergency import commit_emergency, plan_emergency


def _aligned_now() -> datetime:
    """Current UTC rounded up to the next 15-minute grid point (see test_emergency)."""
    now = datetime.now(UTC)
    base = now.replace(minute=0, second=0, microsecond=0)
    steps = math.ceil((now - base).total_seconds() / 60.0 / 15 - 1e-9)
    return base + timedelta(minutes=steps * 15)


_NOW = _aligned_now()


def _rel(minutes: int) -> datetime:
    return _NOW + timedelta(minutes=minutes)


def _mk_patient(db: Session, mrn: str, name: str) -> Patient:
    p = Patient(mrn=mrn, name=name, date_of_birth=date(1990, 1, 1), sex="other")
    db.add(p)
    db.flush()
    return p


@pytest.fixture()
def committed(db_session: Session, user_factory: Callable[..., User]) -> dict[str, int]:
    """Commit an emergency that displaces one booked appointment, via the service."""
    doctor = user_factory(Role.DOCTOR, email="hdoc@cadence.dev")
    nurse = user_factory(Role.TRIAGE_NURSE, email="hnurse@cadence.dev")
    db_session.add(DoctorProfile(user_id=doctor.id, specialty="general"))
    db_session.add(Shift(doctor_id=doctor.id, start_utc=_rel(0), end_utc=_rel(60)))
    appt_type = AppointmentType(name="General", default_duration_min=30, specialty="general")
    booked_patient = _mk_patient(db_session, "CAD-H1", "Booked One")
    emerg_patient = _mk_patient(db_session, "CAD-H2", "Walk-in One")
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
    # The walk-in's acuity must be triaged (A2) before the server will schedule it.
    db_session.add(
        TriageAssessment(
            patient_id=emerg_patient.id,
            nurse_id=nurse.id,
            acuity=Acuity.A2,
            chief_complaint="chest pain",
        )
    )
    db_session.commit()

    now = _NOW
    plan = plan_emergency(
        db_session, patient_id=emerg_patient.id, type_id=appt_type.id, acuity=Acuity.A2, now=now
    )
    result = commit_emergency(
        db_session,
        actor_id=nurse.id,
        patient_id=emerg_patient.id,
        type_id=appt_type.id,
        acuity=Acuity.A2,
        fingerprint=plan["fingerprint"],
        now=now,
    )
    assert result["status"] == "auto"
    return {"decision_id": result["decision_id"], "booked_id": booked.id}


def test_displacements_visible_to_staff(
    client: TestClient,
    committed: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    resp = client.get("/displacements", headers=headers)
    assert resp.status_code == 200
    rows = resp.json()
    row = next(r for r in rows if r["appointment_id"] == committed["booked_id"])
    assert row["decision_id"] == committed["decision_id"]
    assert row["patient_name"] == "Booked One"
    assert row["delay_min"] == 30


def test_decisions_are_admin_only(
    client: TestClient,
    committed: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    assert client.get("/scheduling-decisions", headers=recep).status_code == 403

    admin = auth_headers(user_factory(Role.ADMINISTRATOR))
    resp = client.get("/scheduling-decisions", headers=admin)
    assert resp.status_code == 200
    assert any(d["id"] == committed["decision_id"] for d in resp.json())


def test_decision_detail_is_traceable(
    client: TestClient,
    committed: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    admin = auth_headers(user_factory(Role.ADMINISTRATOR))
    resp = client.get(f"/scheduling-decisions/{committed['decision_id']}", headers=admin)
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["status"] == "auto_committed"
    assert detail["engine_version"].startswith("cadence-engine/")
    assert any(d["appointment_id"] == committed["booked_id"] for d in detail["displacements"])
    assert detail["chosen_plan"] is not None


def test_audit_is_admin_only_and_populated(
    client: TestClient,
    committed: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    recep = auth_headers(user_factory(Role.RECEPTIONIST))
    assert client.get("/audit", headers=recep).status_code == 403

    admin = auth_headers(user_factory(Role.ADMINISTRATOR))
    resp = client.get("/audit", headers=admin)
    assert resp.status_code == 200
    # The commit wrote audit rows (displaced update + emergency creation).
    actions = {a["entity_type"] for a in resp.json()}
    assert "appointment" in actions


# --- escalation resolution (A1) ----------------------------------------------


@pytest.fixture()
def escalated(db_session: Session, user_factory: Callable[..., User]) -> dict[str, int]:
    """Record an escalated (A1) decision via the service — nothing is scheduled."""
    doctor = user_factory(Role.DOCTOR, email="edoc2@cadence.dev")
    nurse = user_factory(Role.TRIAGE_NURSE, email="enurse2@cadence.dev")
    db_session.add(DoctorProfile(user_id=doctor.id, specialty="general"))
    db_session.add(Shift(doctor_id=doctor.id, start_utc=_rel(0), end_utc=_rel(180)))
    appt_type = AppointmentType(name="General", default_duration_min=30, specialty="general")
    patient = _mk_patient(db_session, "CAD-H3", "Critical Carl")
    db_session.add(appt_type)
    db_session.add(
        TriageAssessment(
            patient_id=patient.id,
            nurse_id=nurse.id,
            acuity=Acuity.A1,
            chief_complaint="collapse",
        )
    )
    db_session.commit()

    plan = plan_emergency(
        db_session, patient_id=patient.id, type_id=appt_type.id, acuity=Acuity.A1, now=_NOW
    )
    result = commit_emergency(
        db_session,
        actor_id=nurse.id,
        patient_id=patient.id,
        type_id=appt_type.id,
        acuity=Acuity.A1,
        fingerprint=plan["fingerprint"],
        now=_NOW,
    )
    assert result["status"] == "escalate"
    return {"decision_id": result["decision_id"], "nurse_id": nurse.id}


def test_nurse_can_resolve_an_escalation(
    client: TestClient,
    escalated: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE, email="resolver@cadence.dev"))
    resp = client.post(
        f"/scheduling-decisions/{escalated['decision_id']}/resolve",
        headers=headers,
        json={"note": "Seen by the on-call physician; admitted directly."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == escalated["decision_id"]
    assert body["resolved_at"]
    assert body["resolution_note"].startswith("Seen by")


def test_resolve_requires_a_note(
    client: TestClient,
    escalated: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.ADMINISTRATOR))
    resp = client.post(
        f"/scheduling-decisions/{escalated['decision_id']}/resolve",
        headers=headers,
        json={"note": ""},
    )
    assert resp.status_code == 422  # schema rejects an empty note


def test_resolve_is_forbidden_for_receptionist(
    client: TestClient,
    escalated: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    resp = client.post(
        f"/scheduling-decisions/{escalated['decision_id']}/resolve",
        headers=headers,
        json={"note": "trying"},
    )
    assert resp.status_code == 403


def test_resolve_is_idempotent_guarded(
    client: TestClient,
    escalated: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.ADMINISTRATOR))
    first = client.post(
        f"/scheduling-decisions/{escalated['decision_id']}/resolve",
        headers=headers,
        json={"note": "handled"},
    )
    assert first.status_code == 200
    again = client.post(
        f"/scheduling-decisions/{escalated['decision_id']}/resolve",
        headers=headers,
        json={"note": "again"},
    )
    assert again.status_code == 409
    assert again.json()["error"]["details"]["code"] == "already_resolved"


def test_resolved_escalation_drops_off_the_dashboard(
    client: TestClient,
    escalated: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    admin = auth_headers(user_factory(Role.ADMINISTRATOR))
    before = client.get(
        "/dashboard/summary", headers=admin, params={"now": _NOW.isoformat()}
    ).json()
    assert before["escalations_pending"] >= 1

    client.post(
        f"/scheduling-decisions/{escalated['decision_id']}/resolve",
        headers=admin,
        json={"note": "resolved"},
    )
    after = client.get(
        "/dashboard/summary", headers=admin, params={"now": _NOW.isoformat()}
    ).json()
    assert after["escalations_pending"] == before["escalations_pending"] - 1
    assert all(
        e["decision_id"] != escalated["decision_id"] for e in after["recent_escalations"]
    )
