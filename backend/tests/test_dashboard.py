"""Dashboard tests: pure running-delay logic and the summary endpoint."""

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
from app.scheduling.dashboard import doctor_running_delay
from app.scheduling.queue import QueueItem
from app.services.emergency import commit_emergency, plan_emergency

BASE = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


def _at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _item(start: int, dur: int, status: AppointmentStatus) -> QueueItem:
    return QueueItem(1, 1, _at(start), _at(start + dur), status, Acuity.A5)


# --- pure running-delay -------------------------------------------------------


def test_no_delay_when_on_time() -> None:
    items = [_item(30, 30, AppointmentStatus.BOOKED)]  # future booking
    assert doctor_running_delay(items, _at(0)) == 0


def test_overrunning_consult_counts_as_delay() -> None:
    items = [_item(0, 30, AppointmentStatus.IN_PROGRESS)]  # 09:00-09:30
    assert doctor_running_delay(items, _at(45)) == 15  # 15 min past its end


def test_overdue_waiting_patient_counts_as_delay() -> None:
    items = [_item(0, 30, AppointmentStatus.BOOKED)]  # should have started at 09:00
    assert doctor_running_delay(items, _at(20)) == 20


def test_delay_uses_the_worst_signal() -> None:
    items = [
        _item(0, 15, AppointmentStatus.IN_PROGRESS),  # overran at 09:15
        _item(-30, 30, AppointmentStatus.BOOKED),  # overdue since 08:30
    ]
    # Oldest signal is 08:30; at 09:20 that's 50 minutes behind.
    assert doctor_running_delay(items, _at(20)) == 50


# --- endpoint ----------------------------------------------------------------


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
def setup(db_session: Session, user_factory: Callable[..., User]) -> dict[str, int]:
    doctor = user_factory(Role.DOCTOR, email="ddoc@cadence.dev")
    db_session.add(DoctorProfile(user_id=doctor.id, specialty="general"))
    db_session.add(Shift(doctor_id=doctor.id, start_utc=_rel(0), end_utc=_rel(180)))
    appt_type = AppointmentType(name="General", default_duration_min=30, specialty="general")
    patient = _mk_patient(db_session, "CAD-D1", "Waiting One")
    emerg = _mk_patient(db_session, "CAD-D2", "Walk-in One")
    db_session.add(appt_type)
    db_session.flush()
    db_session.add(
        Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            type_id=appt_type.id,
            scheduled_start=_rel(0),
            scheduled_end=_rel(30),
            version=1,
        )
    )
    db_session.commit()
    return {"doctor_id": doctor.id, "type_id": appt_type.id, "emerg_patient_id": emerg.id}


def test_summary_counts_waiting_and_doctor_load(
    client: TestClient,
    setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    resp = client.get(
        "/dashboard/summary", headers=headers, params={"now": _NOW.isoformat()}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_waiting"] == 1
    assert body["waiting_by_acuity"]["a5"] == 1
    load = next(d for d in body["doctor_load"] if d["doctor_id"] == setup["doctor_id"])
    assert load["waiting"] == 1
    assert load["running_delay_min"] == 0  # starts at now — not yet overdue


def test_summary_lists_pending_escalations(
    client: TestClient,
    setup: dict[str, int],
    db_session: Session,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    nurse = user_factory(Role.TRIAGE_NURSE, email="dnurse@cadence.dev")
    now = _NOW
    # The walk-in's acuity must be triaged before the server will schedule it.
    db_session.add(
        TriageAssessment(
            patient_id=setup["emerg_patient_id"],
            nurse_id=nurse.id,
            acuity=Acuity.A1,
            chief_complaint="collapse",
        )
    )
    db_session.commit()
    plan = plan_emergency(
        db_session,
        patient_id=setup["emerg_patient_id"],
        type_id=setup["type_id"],
        acuity=Acuity.A1,
        now=now,
    )
    commit_emergency(
        db_session,
        actor_id=nurse.id,
        patient_id=setup["emerg_patient_id"],
        type_id=setup["type_id"],
        acuity=Acuity.A1,
        fingerprint=plan["fingerprint"],
        now=now,
    )

    headers = auth_headers(user_factory(Role.ADMINISTRATOR))
    body = client.get(
        "/dashboard/summary", headers=headers, params={"now": now.isoformat()}
    ).json()
    assert body["escalations_pending"] >= 1
    assert any(e["patient_name"] == "Walk-in One" for e in body["recent_escalations"])
