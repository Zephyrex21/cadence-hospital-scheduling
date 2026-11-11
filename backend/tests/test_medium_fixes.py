"""Regression tests for the medium-severity bugs found in the audit."""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import mongomock
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import Acuity, AppointmentStatus, Role
from app.core.mongo import set_mongo_override
from app.core.security import create_refresh_token
from app.main import app
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.decision import SchedulingDecision
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.refresh_token import RefreshToken
from app.models.shift import Shift
from app.models.triage import TriageAssessment

T = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)


def make_doctor(db: Session, user_factory: Any, email: str = "doc@x.dev"):
    doctor = user_factory(Role.DOCTOR, email=email)
    db.add(DoctorProfile(user_id=doctor.id, specialty="general"))
    db.add(Shift(doctor_id=doctor.id, start_utc=T.replace(hour=2), end_utc=T.replace(hour=14)))
    db.commit()
    return doctor


def make_patient(db: Session, n: int, **extra: Any) -> Patient:
    patient = Patient(mrn=f"CAD-7{n:05d}", name=f"Pat {n}", date_of_birth=date(1990, 1, 1),
                      sex="other", **extra)
    db.add(patient)
    db.commit()
    return patient


def make_type(db: Session) -> AppointmentType:
    appt_type = AppointmentType(name="Consult", default_duration_min=30, specialty="general")
    db.add(appt_type)
    db.commit()
    return appt_type


def make_appt(db: Session, doctor: Any, patient: Patient, appt_type: Any, start: datetime,
              status: AppointmentStatus = AppointmentStatus.BOOKED) -> Appointment:
    appt = Appointment(patient_id=patient.id, doctor_id=doctor.id, type_id=appt_type.id,
                       scheduled_start=start, scheduled_end=start + timedelta(minutes=30),
                       status=status, acuity=Acuity.A5)
    db.add(appt)
    db.commit()
    return appt


# --- 7. strangers cannot lock the real owner out ---


def test_a_flood_of_wrong_passwords_cannot_lock_out_the_real_owner(
    client: TestClient, user_factory: Any
) -> None:
    user_factory(Role.ADMINISTRATOR, email="admin-lock@cadence.dev")
    for i in range(1, 6):  # five addresses x five failures = 25 > the per-email flood limit (20)
        stranger = TestClient(app, client=(f"10.7.0.{i}", 1234))
        for _ in range(5):
            stranger.post("/auth/login", json={"email": "admin-lock@cadence.dev",
                                               "password": "wrong"})
    owner = TestClient(app, client=("10.7.0.99", 1234))
    # during the flood a wrong guess is throttled…
    guess = owner.post("/auth/login", json={"email": "admin-lock@cadence.dev", "password": "nope"})
    assert guess.status_code == 429
    # …but the correct password still gets in
    ok = owner.post("/auth/login",
                    json={"email": "admin-lock@cadence.dev", "password": "secret123"})
    assert ok.status_code == 200, ok.text


def test_one_client_is_still_blocked_after_a_few_failures(
    client: TestClient, user_factory: Any
) -> None:
    user_factory(Role.RECEPTIONIST, email="pair@x.dev")
    attacker = TestClient(app, client=("10.8.0.1", 1))
    codes = [attacker.post("/auth/login", json={"email": "pair@x.dev", "password": "x"}).status_code
             for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[-1] == 429


# --- 8. unknown and known emails take the same time ---


def test_login_timing_does_not_reveal_which_emails_exist(
    client: TestClient, user_factory: Any
) -> None:
    user_factory(Role.RECEPTIONIST, email="known@x.dev")

    def avg(email: str, base: int) -> float:
        start = time.perf_counter()
        for i in range(4):
            TestClient(app, client=(f"10.9.{base}.{i}", 1)).post(
                "/auth/login", json={"email": email, "password": "wrong"})
        return (time.perf_counter() - start) / 4

    known, unknown = avg("known@x.dev", 1), avg("nobody@x.dev", 2)
    assert unknown > known * 0.5, f"known {known * 1000:.0f} ms vs unknown {unknown * 1000:.0f} ms"


# --- 9. refresh tokens are single-use ---


def _login(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/auth/login", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200, resp.text
    body: dict[str, str] = resp.json()
    return body


def test_a_refresh_token_works_once_and_rotates(
    client: TestClient, db_session: Session, user_factory: Any
) -> None:
    user_factory(Role.RECEPTIONIST, email="rot@x.dev")
    first = _login(client, "rot@x.dev")
    assert db_session.scalars(select(RefreshToken)).all(), "issued tokens are recorded"

    second = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert second.status_code == 200
    assert second.json()["refresh_token"] != first["refresh_token"]
    # immediately reusing the old one (e.g. two tabs at once) is refused but harmless…
    assert client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}
                       ).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": second.json()["refresh_token"]}
                       ).status_code == 200


def test_reusing_a_stolen_refresh_token_later_revokes_the_whole_family(
    client: TestClient, user_factory: Any
) -> None:
    user_factory(Role.RECEPTIONIST, email="theft@x.dev")
    original = _login(client, "theft@x.dev")
    rotated = client.post("/auth/refresh", json={"refresh_token": original["refresh_token"]}).json()
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=5), tick=False):
        replay = client.post("/auth/refresh", json={"refresh_token": original["refresh_token"]})
        assert replay.status_code == 401 and "reuse" in replay.json()["error"]["message"].lower()
        # the legitimate holder's newer token is dead too: everyone must sign in again
        assert client.post("/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
                           ).status_code == 401


def test_logout_revokes_the_refresh_token(client: TestClient, user_factory: Any) -> None:
    user_factory(Role.RECEPTIONIST, email="out@x.dev")
    pair = _login(client, "out@x.dev")
    assert client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]}
                       ).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}
                       ).status_code == 401
    # signing out with garbage is silently fine
    assert client.post("/auth/logout", json={"refresh_token": "junk"}).status_code == 204


def test_tokens_issued_before_rotation_existed_still_work_once(
    client: TestClient, user_factory: Any
) -> None:
    user = user_factory(Role.RECEPTIONIST, email="legacy@x.dev")
    old = create_refresh_token(str(user.id), user.role.value)  # no id, as an old deployment issued
    assert client.post("/auth/refresh", json={"refresh_token": old}).status_code == 200


# --- 10. queue waits respect the appointment time ---


def test_queue_wait_estimate_does_not_ignore_when_a_patient_is_due(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = make_doctor(db_session, user_factory)
        appt_type = make_type(db_session)
        soon = make_appt(db_session, doctor, make_patient(db_session, 1), appt_type,
                         T + timedelta(minutes=5))
        far = make_appt(db_session, doctor, make_patient(db_session, 2), appt_type,
                        T + timedelta(hours=5))
        queue = {e["appointment_id"]: e for e in
                 client.get("/queue", headers=auth_headers(doctor)).json()}
        assert queue[soon.id]["est_wait_min"] == 5
        assert queue[far.id]["est_wait_min"] == 300  # booked for 15:00, not "next in line"
        assert queue[far.id]["position"] == 2


def test_patients_who_are_here_are_served_in_acuity_order(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = make_doctor(db_session, user_factory)
        appt_type = make_type(db_session)
        routine = make_appt(db_session, doctor, make_patient(db_session, 3), appt_type, T,
                            AppointmentStatus.CHECKED_IN)
        urgent = make_appt(db_session, doctor, make_patient(db_session, 4), appt_type,
                           T + timedelta(minutes=30), AppointmentStatus.CHECKED_IN)
        urgent.acuity = Acuity.A2
        db_session.commit()
        queue = {e["appointment_id"]: e for e in
                 client.get("/queue", headers=auth_headers(doctor)).json()}
        assert queue[urgent.id]["position"] == 1 and queue[urgent.id]["est_wait_min"] == 0
        assert queue[routine.id]["position"] == 2 and queue[routine.id]["est_wait_min"] == 30


# --- 11. "waiting" means here, not merely booked ---


def test_dashboard_only_counts_patients_who_are_here_or_due_as_waiting(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = make_doctor(db_session, user_factory)
        appt_type = make_type(db_session)
        make_appt(db_session, doctor, make_patient(db_session, 5), appt_type,
                  T + timedelta(hours=4))
        arrived = make_appt(db_session, doctor, make_patient(db_session, 6), appt_type,
                            T + timedelta(hours=3))
        due = make_appt(db_session, doctor, make_patient(db_session, 7), appt_type,
                        T - timedelta(minutes=10))
        headers = auth_headers(doctor)

        summary = client.get("/dashboard/summary", headers=headers).json()
        assert summary["total_waiting"] == 1  # only the one whose time has come
        assert sum(summary["waiting_by_acuity"].values()) == 1

        arrived.status = AppointmentStatus.CHECKED_IN
        db_session.commit()
        summary = client.get("/dashboard/summary", headers=headers).json()
        assert summary["total_waiting"] == 2
        load = next(d for d in summary["doctor_load"] if d["doctor_id"] == doctor.id)
        assert load["waiting"] == 2
        assert due.id  # (the due one is the second waiting patient)


# --- 12. the patient list can be paged and counted ---


def test_patient_list_pages_and_counts(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    for i in range(60):
        make_patient(db_session, 100 + i)
    headers = auth_headers(user_factory(Role.ADMINISTRATOR))
    assert client.get("/patients/count", headers=headers).json() == {"total": 60}
    first = client.get("/patients", headers=headers, params={"limit": 50}).json()
    rest = client.get("/patients", headers=headers, params={"limit": 50, "offset": 50}).json()
    assert len(first) == 50 and len(rest) == 10
    assert len({p["id"] for p in first + rest}) == 60  # no overlap, nothing missing
    assert client.get("/patients", headers=headers, params={"limit": 500}).status_code == 422
    searched = client.get("/patients/count", headers=headers, params={"q": "Pat 10"})
    assert searched.json()["total"] > 0


def test_search_treats_percent_and_underscore_literally(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    make_patient(db_session, 1, city="Pune")
    headers = auth_headers(user_factory(Role.ADMINISTRATOR))
    assert client.get("/patients", headers=headers, params={"q": "%"}).json() == []
    assert client.get("/patients", headers=headers, params={"q": "P_ne"}).json() == []
    assert len(client.get("/patients", headers=headers, params={"q": "Pune"}).json()) == 1


# --- 13. patient input is validated ---


def test_patient_input_is_validated(
    client: TestClient, user_factory: Any, auth_headers: Any
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    base = {"name": "Asha Rao", "date_of_birth": "1990-01-01", "sex": "female"}

    def post(**override: Any) -> int:
        return client.post("/patients", headers=headers, json={**base, **override}).status_code

    assert post() == 201
    assert post(date_of_birth="2099-01-01") == 422  # future
    assert post(date_of_birth="1850-01-01") == 422  # implausibly old
    assert post(sex="banana") == 422
    assert post(sex="Female") == 422  # the API takes the canonical lowercase value
    assert post(blood_group="ZZ") == 422
    assert post(name="A") == 422
    # blank optional fields are fine and are stored as nothing
    created = client.post("/patients", headers=headers,
                          json={**base, "name": "  Ravi   Kumar ", "blood_group": "", "city": "  "})
    assert created.status_code == 201
    assert created.json()["name"] == "Ravi Kumar"
    assert created.json()["blood_group"] is None and created.json()["city"] is None
    assert post(blood_group="AB-") == 201


# --- 14. one open escalation per patient ---


def _a1_request(client: TestClient, db: Session, user_factory: Any, auth_headers: Any):
    doctor = make_doctor(db, user_factory)
    appt_type = make_type(db)
    patient = make_patient(db, 300)
    db.add(TriageAssessment(patient_id=patient.id, nurse_id=doctor.id, acuity=Acuity.A1,
                            chief_complaint="chest pain"))
    db.commit()
    headers = auth_headers(user_factory(Role.TRIAGE_NURSE))
    body = {"patient_id": patient.id, "type_id": appt_type.id, "acuity": "a1", "now": T.isoformat()}
    plan = client.post("/emergencies/plan", headers=headers, json=body).json()
    return headers, {**body, "fingerprint": plan["fingerprint"]}


def test_a_patient_cannot_have_two_open_escalations(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        headers, body = _a1_request(client, db_session, user_factory, auth_headers)
        first = client.post("/emergencies/commit", headers=headers,
                            json={**body, "idempotency_key": "click-1"})
        assert first.status_code == 200
        second = client.post("/emergencies/commit", headers=headers,
                             json={**body, "idempotency_key": "click-2"})
        assert second.status_code == 409
        assert "open escalation" in second.json()["error"]["message"]
        assert len(list(db_session.scalars(select(SchedulingDecision)))) == 1

        # once it is resolved, a new escalation for the patient is allowed again
        record = db_session.scalar(select(SchedulingDecision))
        assert record is not None
        resolved = client.post(f"/scheduling-decisions/{record.id}/resolve", headers=headers,
                               json={"note": "handled manually at the bedside"})
        assert resolved.status_code == 200, resolved.text
        third = client.post("/emergencies/commit", headers=headers,
                            json={**body, "idempotency_key": "click-3"})
        assert third.status_code == 200, third.text


# --- 15. a duplicate employee id is a conflict, not an outage ---


def test_duplicate_employee_id_is_a_conflict(
    client: TestClient, user_factory: Any, auth_headers: Any
) -> None:
    from app.mongo.schema import ensure_indexes

    database = mongomock.MongoClient().medium_fix
    ensure_indexes(database)
    set_mongo_override(database)
    try:
        admin = auth_headers(user_factory(Role.ADMINISTRATOR))
        a = user_factory(Role.TRIAGE_NURSE, email="n1@x.dev")
        b = user_factory(Role.TRIAGE_NURSE, email="n2@x.dev")
        assert client.put(f"/staff/{a.id}/profile", headers=admin,
                          json={"employee_id": "NUR-9"}).status_code == 200
        clash = client.put(f"/staff/{b.id}/profile", headers=admin, json={"employee_id": "NUR-9"})
        assert clash.status_code == 409
        assert "already used" in clash.json()["error"]["message"]
    finally:
        set_mongo_override(None)
