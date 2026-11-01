"""Regression tests for the critical defects found in the project review.

Each test pins a behaviour that used to be broken: double-booking, escalations that
could never be scheduled, patients in two rooms, the UTC-midnight blind spot, a
client-controlled clock, triage re-use, un-bound idempotency keys, login brute
force and the insecure JWT default.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.core.enums import Acuity, AppointmentOrigin, AppointmentStatus, Role
from app.core.errors import ConflictError
from app.models.appointment import Appointment
from app.models.appointment_type import AppointmentType
from app.models.base import utcnow
from app.models.decision import SchedulingDecision
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.triage import TriageAssessment
from app.models.user import User
from app.schemas.scheduling import AppointmentCreate
from app.services.scheduling import book_appointment
from tests.test_emergency import (
    _mk_doctor,
    _mk_patient,
    _plan_body,
    _rel,
    _triage,
)

IS_POSTGRES = bool(os.environ.get("CADENCE_TEST_DATABASE_URL"))


def _type(db: Session, minutes: int = 30) -> AppointmentType:
    t = AppointmentType(name=f"General{minutes}", default_duration_min=minutes, specialty="general")
    db.add(t)
    db.flush()
    return t


def _book(db: Session, doctor_id: int, patient_id: int, type_id: int, start: datetime,
          dur: int = 30) -> Appointment:
    a = Appointment(
        patient_id=patient_id, doctor_id=doctor_id, type_id=type_id,
        scheduled_start=start, scheduled_end=start + timedelta(minutes=dur),
        status=AppointmentStatus.BOOKED, origin=AppointmentOrigin.BOOKED, version=1,
    )
    db.add(a)
    db.commit()
    return a


def _overlaps(a: Appointment, b: Appointment) -> bool:
    return a.scheduled_start < b.scheduled_end and b.scheduled_start < a.scheduled_end


def _plan_and_commit(
    client: TestClient, headers: dict[str, str], setup: dict[str, int], acuity: str,
    **extra: Any,
) -> tuple[dict[str, Any], Any]:
    plan = client.post("/emergencies/plan", headers=headers, json=_plan_body(setup, acuity)).json()
    body = _plan_body(setup, acuity)
    body["fingerprint"] = plan["fingerprint"]
    body["plan_digest"] = plan["plan_digest"]
    body.update(extra)
    return plan, client.post("/emergencies/commit", headers=headers, json=body)


@pytest.fixture()
def one_doctor(db_session: Session, user_factory: Callable[..., User]) -> dict[str, int]:
    doc = _mk_doctor(db_session, user_factory, "edoc@cadence.dev")
    db_session.add(Shift(doctor_id=doc.id, start_utc=_rel(0), end_utc=_rel(240)))
    t = _type(db_session)
    pt = _mk_patient(db_session, "CAD-F1", "Fix Patient")
    db_session.commit()
    return {"doctor_id": doc.id, "type_id": t.id, "patient_id": pt.id}


# --- 1. Double-booking is impossible at the database level --------------------------------
def test_db_refuses_overlapping_appointments_for_doctor_and_patient(
    db_session: Session, user_factory: Callable[..., User]
) -> None:
    d1 = _mk_doctor(db_session, user_factory, "d1@x.dev")
    d2 = _mk_doctor(db_session, user_factory, "d2@x.dev")
    t = _type(db_session)
    p1 = _mk_patient(db_session, "CAD-O1", "One")
    p2 = _mk_patient(db_session, "CAD-O2", "Two")
    db_session.commit()
    _book(db_session, d1.id, p1.id, t.id, _rel(30))
    with pytest.raises(IntegrityError):  # same doctor, overlapping time
        _book(db_session, d1.id, p2.id, t.id, _rel(45))
    db_session.rollback()
    with pytest.raises(IntegrityError):  # same patient, other doctor, overlapping time
        _book(db_session, d2.id, p1.id, t.id, _rel(30))
    db_session.rollback()
    # Back-to-back is fine, and a cancelled appointment frees the slot.
    _book(db_session, d1.id, p2.id, t.id, _rel(60))
    first = db_session.scalars(select(Appointment).where(Appointment.patient_id == p1.id)).one()
    first.status = AppointmentStatus.CANCELLED
    db_session.commit()
    _book(db_session, d1.id, p2.id, t.id, _rel(120))


def test_booking_race_cannot_double_book(tmp_path: Any) -> None:
    """Both requests pass the app-level check before either inserts (forced with a
    barrier) — the database guard must still let exactly one win."""
    import app.models  # noqa: F401
    import app.services.scheduling as svc
    from app.core.db import Base
    from app.core.security import hash_password
    from app.models.doctor import DoctorProfile

    eng = create_engine(
        f"sqlite+pysqlite:///{tmp_path}/race.db",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with factory() as s:
        doc = User(name="D", email="d@x.dev", role=Role.DOCTOR, password_hash=hash_password("x"))
        s.add(doc)
        s.flush()
        s.add(DoctorProfile(user_id=doc.id, specialty="general"))
        s.add(Shift(doctor_id=doc.id, start_utc=_rel(0), end_utc=_rel(240)))
        ty = AppointmentType(name="G", default_duration_min=30, specialty="general")
        s.add(ty)
        pats = [
            Patient(mrn=f"CAD-R{i}", name=f"R{i}", date_of_birth=date(1990, 1, 1), sex="x")
            for i in range(2)
        ]
        s.add_all(pats)
        s.commit()
        doc_id, ty_id, pids = doc.id, ty.id, [p.id for p in pats]

    barrier = threading.Barrier(2)
    real = svc.has_conflict

    def slow_has_conflict(c: Any, busy: Any) -> bool:
        result = real(c, busy)
        if not busy:  # only the "free slot" answers race
            try:
                barrier.wait(timeout=3)
            except threading.BrokenBarrierError:
                pass
        return result

    results: list[str] = []

    def worker(pid: int) -> None:
        with factory() as s:
            try:
                svc.book_appointment(
                    s,
                    AppointmentCreate(patient_id=pid, doctor_id=doc_id, type_id=ty_id,
                                      scheduled_start=_rel(60)),
                    actor_id=1,
                )
                results.append("ok")
            except ConflictError:
                results.append("conflict")

    svc.has_conflict = slow_has_conflict  # type: ignore[assignment]
    try:
        threads = [threading.Thread(target=worker, args=(p,)) for p in pids]
        [t.start() for t in threads]
        [t.join() for t in threads]
    finally:
        svc.has_conflict = real  # type: ignore[assignment]
    with factory() as s:
        count = s.scalar(select(func.count()).select_from(Appointment))
    assert sorted(results) == ["conflict", "ok"]
    assert count == 1


@pytest.mark.skipif(not IS_POSTGRES, reason="needs real PostgreSQL concurrency")
def test_concurrent_bookings_on_postgres_allow_exactly_one(
    db_session: Session, user_factory: Callable[..., User]
) -> None:
    doc = _mk_doctor(db_session, user_factory, "pgdoc@x.dev")
    db_session.add(Shift(doctor_id=doc.id, start_utc=_rel(0), end_utc=_rel(240)))
    t = _type(db_session)
    pats = [_mk_patient(db_session, f"CAD-PG{i}", f"PG{i}") for i in range(8)]
    db_session.commit()
    doc_id, type_id, pids = doc.id, t.id, [p.id for p in pats]
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, expire_on_commit=False)
    results: list[str] = []
    gate = threading.Barrier(len(pids))

    def worker(pid: int) -> None:
        with factory() as s:
            gate.wait()
            try:
                book_appointment(
                    s,
                    AppointmentCreate(patient_id=pid, doctor_id=doc_id, type_id=type_id,
                                      scheduled_start=_rel(60)),
                    actor_id=1,
                )
                results.append("ok")
            except ConflictError:
                results.append("conflict")

    threads = [threading.Thread(target=worker, args=(p,)) for p in pids]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count("ok") == 1 and results.count("conflict") == len(pids) - 1


@pytest.mark.skipif(not IS_POSTGRES, reason="needs real PostgreSQL concurrency")
def test_concurrent_emergency_commits_never_overlap_on_postgres(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    doc = _mk_doctor(db_session, user_factory, "pgdoc2@x.dev")
    db_session.add(Shift(doctor_id=doc.id, start_utc=_rel(0), end_utc=_rel(240)))
    t = _type(db_session)
    pats = [_mk_patient(db_session, f"CAD-EM{i}", f"EM{i}") for i in range(2)]
    db_session.commit()
    nurse = user_factory(Role.TRIAGE_NURSE)
    for p in pats:
        _triage(db_session, p.id, "a3", nurse_id=nurse.id)
    h = auth_headers(nurse)
    bodies = []
    for p in pats:
        setup = {"doctor_id": doc.id, "type_id": t.id, "patient_id": p.id}
        plan = client.post("/emergencies/plan", headers=h, json=_plan_body(setup, "a3")).json()
        body = _plan_body(setup, "a3")
        body["fingerprint"] = plan["fingerprint"]
        bodies.append(body)
    from app.core.db import get_db
    from app.main import app

    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, expire_on_commit=False)

    def per_request_db() -> Any:
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = per_request_db
    codes: list[int] = []
    gate = threading.Barrier(2)

    def worker(body: dict[str, Any]) -> None:
        gate.wait()
        codes.append(client.post("/emergencies/commit", headers=h, json=body).status_code)

    threads = [threading.Thread(target=worker, args=(b,)) for b in bodies]
    [x.start() for x in threads]
    [x.join() for x in threads]
    db_session.expire_all()
    rows = list(db_session.scalars(select(Appointment)))
    assert not any(_overlaps(a, b) for i, a in enumerate(rows) for b in rows[i + 1:])
    assert 200 in codes  # at least one succeeded; the other was refused or re-planned


# --- 2. Escalations (A1 and others) can now actually be scheduled -------------------------
def test_a1_escalation_can_be_reviewed_and_applied(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]], one_doctor: dict[str, int],
) -> None:
    nurse = user_factory(Role.TRIAGE_NURSE)
    h = auth_headers(nurse)
    _triage(db_session, one_doctor["patient_id"], "a1")
    _, res = _plan_and_commit(client, h, one_doctor, "a1")
    body = res.json()
    assert body["status"] == "escalate" and body["emergency_appointment_id"] is None
    did = body["decision_id"]

    opts = client.get(f"/escalations/{did}/options", headers=h).json()
    assert opts["options"] and opts["options"][0]["applicable"] is True

    applied = client.post(f"/escalations/{did}/apply", headers=h, json={"option_index": 0})
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    appt = db_session.get(Appointment, applied.json()["emergency_appointment_id"])
    assert appt is not None and appt.origin == AppointmentOrigin.EMERGENCY
    assert appt.acuity == Acuity.A1 and appt.patient_id == one_doctor["patient_id"]

    record = db_session.get(SchedulingDecision, did)
    db_session.refresh(record)
    assert record is not None and record.resolved_at is not None
    assert record.emergency_appointment_id == appt.id
    # Applying twice is refused, and the triage is spent.
    again = client.post(f"/escalations/{did}/apply", headers=h, json={"option_index": 0})
    assert again.status_code == 409


def test_apply_requires_clinician_and_rejects_unsafe_options(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]], one_doctor: dict[str, int],
) -> None:
    nurse_h = auth_headers(user_factory(Role.TRIAGE_NURSE))
    recep_h = auth_headers(user_factory(Role.RECEPTIONIST))
    _triage(db_session, one_doctor["patient_id"], "a1")
    _, res = _plan_and_commit(client, nurse_h, one_doctor, "a1")
    did = res.json()["decision_id"]
    assert client.post(f"/escalations/{did}/apply", headers=recep_h,
                       json={"option_index": 0}).status_code == 403
    assert client.get(f"/escalations/{did}/options", headers=recep_h).status_code == 403
    assert client.post(f"/escalations/{did}/apply", headers=nurse_h,
                       json={"option_index": 99}).status_code == 422


def test_apply_refuses_when_schedule_changed_since_proposal(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]], one_doctor: dict[str, int],
) -> None:
    h = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, one_doctor["patient_id"], "a1")
    _, res = _plan_and_commit(client, h, one_doctor, "a1")
    did = res.json()["decision_id"]
    other = _mk_patient(db_session, "CAD-F9", "Someone Else")
    db_session.commit()
    # Someone books the proposed slot before the clinician approves.
    _book(db_session, one_doctor["doctor_id"], other.id, one_doctor["type_id"], _rel(0))
    r = client.post(f"/escalations/{did}/apply", headers=h, json={"option_index": 0})
    assert r.status_code == 409
    assert db_session.scalar(
        select(func.count()).select_from(Appointment)
        .where(Appointment.patient_id == one_doctor["patient_id"])
    ) == 0


# --- 3. A patient is never placed in two rooms at once -----------------------------------
def test_ripple_never_double_books_a_patient_across_doctors(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    d1 = _mk_doctor(db_session, user_factory, "d1@x.dev")
    d2 = _mk_doctor(db_session, user_factory, "d2@x.dev")
    for d in (d1, d2):
        db_session.add(Shift(doctor_id=d.id, start_utc=_rel(0), end_utc=_rel(240)))
    t = _type(db_session)
    P = _mk_patient(db_session, "CAD-X0", "Patient P")
    X = _mk_patient(db_session, "CAD-X1", "Other X")
    E = _mk_patient(db_session, "CAD-X2", "Emergency E")
    db_session.commit()
    a = _book(db_session, d1.id, P.id, t.id, _rel(0))
    _book(db_session, d2.id, X.id, t.id, _rel(0))
    c = _book(db_session, d2.id, P.id, t.id, _rel(30))
    h = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, E.id, "a2")
    setup = {"doctor_id": d1.id, "type_id": t.id, "patient_id": E.id}
    _, res = _plan_and_commit(client, h, setup, "a2")
    assert res.status_code == 200, res.text
    db_session.expire_all()
    assert not _overlaps(db_session.get(Appointment, a.id), db_session.get(Appointment, c.id))  # type: ignore[arg-type]


def test_emergency_patient_cannot_overlap_their_own_appointment(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]], one_doctor: dict[str, int],
) -> None:
    _book(db_session, one_doctor["doctor_id"], one_doctor["patient_id"],
          one_doctor["type_id"], _rel(0))
    h = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, one_doctor["patient_id"], "a3")
    plan = client.post("/emergencies/plan", headers=h, json=_plan_body(one_doctor, "a3")).json()
    chosen = plan["decision"]["chosen"]
    if chosen is not None:
        start = datetime.fromisoformat(chosen["placement"]["start"])
        assert start >= _rel(30)  # never on top of their own 00:00-00:30 appointment


# --- 4. UTC midnight is not a blind spot --------------------------------------------------
def test_engine_sees_appointments_after_utc_midnight(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    d = _mk_doctor(db_session, user_factory, "night@x.dev")
    now = utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    midnight = now + timedelta(minutes=15)  # an appointment just after the placement start
    db_session.add(Shift(doctor_id=d.id, start_utc=now - timedelta(hours=2),
                         end_utc=now + timedelta(hours=6)))
    t = _type(db_session)
    P = _mk_patient(db_session, "CAD-N0", "Booked Soon")
    E = _mk_patient(db_session, "CAD-N1", "Walk In")
    db_session.commit()
    booked = _book(db_session, d.id, P.id, t.id, midnight)
    nurse = user_factory(Role.TRIAGE_NURSE)
    _triage(db_session, E.id, "a3", nurse_id=nurse.id)
    h = auth_headers(nurse)
    body = {"patient_id": E.id, "type_id": t.id, "acuity": "a3", "now": now.isoformat()}
    chosen = client.post("/emergencies/plan", headers=h, json=body).json()["decision"]["chosen"]
    start = datetime.fromisoformat(chosen["placement"]["start"])
    end = datetime.fromisoformat(chosen["placement"]["end"])
    overlaps_booked = start < booked.scheduled_end and booked.scheduled_start < end
    assert not overlaps_booked or any(
        m["appointment_id"] == booked.id and datetime.fromisoformat(m["to_start"]) >= end
        for m in chosen["moves"]
    )


def test_horizon_covers_appointments_across_midnight() -> None:
    from app.scheduling.engine_adapter import _horizon

    now = datetime(2026, 10, 29, 23, 45, tzinfo=UTC)
    lo, hi = _horizon(now)
    assert lo < datetime(2026, 10, 29, 12, 0, tzinfo=UTC) < now
    assert now < datetime(2026, 10, 30, 12, 0, tzinfo=UTC) < hi


# --- 5. The server clock is authoritative -------------------------------------------------
def test_client_supplied_now_is_ignored_unless_explicitly_allowed(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]], one_doctor: dict[str, int],
) -> None:
    settings.allow_client_now = False
    h = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, one_doctor["patient_id"], "a2")
    body = _plan_body(one_doctor, "a2")
    body["now"] = (utcnow() + timedelta(hours=3)).isoformat()
    plan = client.post("/emergencies/plan", headers=h, json=body).json()
    assert abs((datetime.fromisoformat(plan["now"]) - utcnow()).total_seconds()) < 30


def test_commit_places_emergency_at_server_now_never_in_the_past(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    real_now = utcnow()
    doc = _mk_doctor(db_session, user_factory, "clk@x.dev")
    db_session.add(Shift(doctor_id=doc.id, start_utc=real_now - timedelta(hours=1),
                         end_utc=real_now + timedelta(hours=4)))
    t = _type(db_session)
    pt = _mk_patient(db_session, "CAD-C1", "Clock Patient")
    db_session.commit()
    _triage(db_session, pt.id, "a2")
    settings.allow_client_now = False
    h = auth_headers(user_factory(Role.TRIAGE_NURSE))
    stale = (real_now - timedelta(minutes=9, seconds=30)).isoformat()
    setup = {"doctor_id": doc.id, "type_id": t.id, "patient_id": pt.id}
    body = {"patient_id": pt.id, "type_id": t.id, "acuity": "a2", "now": stale}
    plan = client.post("/emergencies/plan", headers=h, json=body).json()
    body.update(fingerprint=plan["fingerprint"], plan_digest=plan["plan_digest"])
    res = client.post("/emergencies/commit", headers=h, json=body)
    assert res.status_code == 200, res.text
    appt = db_session.get(Appointment, res.json()["emergency_appointment_id"])
    assert appt is not None and appt.scheduled_start >= real_now - timedelta(seconds=5)
    assert setup  # (kept for readability)


def test_commit_refuses_when_reviewed_plan_changed(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]], one_doctor: dict[str, int],
) -> None:
    h = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, one_doctor["patient_id"], "a3")
    _, res = _plan_and_commit(client, h, one_doctor, "a3", plan_digest="0" * 64)
    assert res.status_code == 409
    assert res.json()["error"]["details"]["code"] == "plan_changed"


# --- 6. One triage, one emergency --------------------------------------------------------
def test_triage_is_consumed_by_a_committed_emergency(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]], one_doctor: dict[str, int],
) -> None:
    h = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, one_doctor["patient_id"], "a3")
    _, first = _plan_and_commit(client, h, one_doctor, "a3")
    assert first.status_code == 200 and first.json()["status"] == "auto"
    plan = client.post("/emergencies/plan", headers=h, json=_plan_body(one_doctor, "a3"))
    assert plan.status_code == 422
    assert plan.json()["error"]["details"]["code"] == "triage_required"
    latest = client.get(f"/patients/{one_doctor['patient_id']}/latest-triage", headers=h)
    assert latest.json() is None
    row = db_session.scalars(select(TriageAssessment)).one()
    db_session.refresh(row)
    assert row.consumed_at is not None


# --- 7. Idempotency keys are bound to their request ---------------------------------------
def test_idempotency_key_cannot_be_reused_for_a_different_patient(
    client: TestClient, db_session: Session, user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]], one_doctor: dict[str, int],
) -> None:
    bob = _mk_patient(db_session, "CAD-K2", "Bob")
    db_session.commit()
    h = auth_headers(user_factory(Role.TRIAGE_NURSE))
    _triage(db_session, one_doctor["patient_id"], "a3")
    _triage(db_session, bob.id, "a3")
    _, first = _plan_and_commit(client, h, one_doctor, "a3", idempotency_key="k-1")
    assert first.status_code == 200
    # Same request again → same stored result (true replay).
    replay = client.post("/emergencies/commit", headers=h, json={
        **_plan_body(one_doctor, "a3"), "fingerprint": "x", "idempotency_key": "k-1"})
    assert replay.status_code == 200 and replay.json()["decision_id"] == first.json()["decision_id"]
    # Different patient, same key → refused, never someone else's result.
    other = {**one_doctor, "patient_id": bob.id}
    plan = client.post("/emergencies/plan", headers=h, json=_plan_body(other, "a3")).json()
    res = client.post("/emergencies/commit", headers=h, json={
        **_plan_body(other, "a3"), "fingerprint": plan["fingerprint"], "idempotency_key": "k-1"})
    assert res.status_code == 409
    assert res.json()["error"]["details"]["code"] == "idempotency_key_reused"
    assert db_session.scalar(
        select(func.count()).select_from(Appointment).where(Appointment.patient_id == bob.id)
    ) == 0


# --- 8. Login brute force is throttled ----------------------------------------------------
def test_login_is_throttled_after_repeated_failures(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user_factory(Role.DOCTOR, email="victim@x.dev", password="correct-horse")
    for _ in range(settings.login_max_attempts):
        r = client.post("/auth/login", json={"email": "victim@x.dev", "password": "nope"})
        assert r.status_code == 401
    blocked = client.post(
        "/auth/login", json={"email": "victim@x.dev", "password": "correct-horse"}
    )
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers


def test_successful_login_resets_the_failure_counter(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user_factory(Role.DOCTOR, email="ok@x.dev", password="correct-horse")
    for _ in range(settings.login_max_attempts - 1):
        client.post("/auth/login", json={"email": "ok@x.dev", "password": "nope"})
    assert client.post("/auth/login", json={"email": "ok@x.dev",
                                            "password": "correct-horse"}).status_code == 200
    for _ in range(settings.login_max_attempts - 1):
        assert client.post("/auth/login", json={"email": "ok@x.dev",
                                                "password": "nope"}).status_code == 401


# --- 9. No usable default JWT secret ------------------------------------------------------
def test_production_refuses_missing_or_weak_jwt_secret() -> None:
    for bad in ("", "dev-insecure-secret-change-me", "short"):
        with pytest.raises(ValueError):
            Settings(env="production", jwt_secret=bad, _env_file=None)  # type: ignore[call-arg]
    ok = Settings(env="production", jwt_secret="x" * 40, _env_file=None)  # type: ignore[call-arg]
    assert ok.jwt_secret == "x" * 40


def test_production_refuses_client_clock() -> None:
    with pytest.raises(ValueError):
        Settings(  # type: ignore[call-arg]
            env="production", jwt_secret="x" * 40, allow_client_now=True, _env_file=None
        )


def test_dev_without_secret_gets_random_not_the_published_default() -> None:
    a = Settings(env="development", jwt_secret="", _env_file=None)  # type: ignore[call-arg]
    b = Settings(env="development", jwt_secret="dev-insecure-secret-change-me",  # type: ignore[call-arg]
                 _env_file=None)
    assert a.jwt_secret != b.jwt_secret
    assert "dev-insecure" not in a.jwt_secret + b.jwt_secret and len(a.jwt_secret) >= 32


def test_seed_refuses_demo_password_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.seed as seed_mod

    monkeypatch.setattr(seed_mod.settings, "env", "production")
    monkeypatch.setattr(seed_mod.settings, "seed_password", None)
    with pytest.raises(SystemExit):
        seed_mod._seed_password()


# --- 10. Startup auto-migration (a deploy must not need a manual `alembic upgrade`) ----------
def test_run_migrations_upgrades_an_old_schema_and_cancels_existing_overlaps(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3

    from alembic import command
    from app.core import migrate

    db_file = tmp_path / "old.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+pysqlite:///{db_file}")
    cfg = migrate._alembic_config()
    command.upgrade(cfg, "0004")  # the schema a not-yet-redeployed database has

    def columns(con: sqlite3.Connection) -> list[str]:
        return [r[1] for r in con.execute("PRAGMA table_info(scheduling_decisions)")]

    appt_insert = (
        "INSERT INTO appointments (id,patient_id,doctor_id,type_id,scheduled_start,scheduled_end,"
        "status,origin,acuity,displacement_count,version,created_at,updated_at) "
        "VALUES (?,?,1,1,?,?,'booked','booked','a5',0,1,?,?)"
    )
    ts = "2026-10-30 10:00:00.000000"
    con = sqlite3.connect(db_file)
    assert "request_hash" not in columns(con)
    con.execute(
        "INSERT INTO users (id,name,email,password_hash,role,is_active,created_at,updated_at) "
        "VALUES (1,'D','d@x.dev','x','doctor',1,?,?)",
        (ts, ts),
    )
    for pid in (1, 2):
        con.execute(
            "INSERT INTO patients (id,mrn,name,date_of_birth,sex,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (pid, f"M{pid}", f"P{pid}", "1990-01-01", "x", ts, ts),
        )
    con.execute(
        "INSERT INTO appointment_types (id,name,default_duration_min,specialty) "
        "VALUES (1,'G',30,'general')"
    )
    # Two ACTIVE appointments for the same doctor that overlap: invalid, pre-existing data.
    first = ("2026-11-01 09:00:00.000000", "2026-11-01 09:30:00.000000")
    second = ("2026-11-01 09:15:00.000000", "2026-11-01 09:45:00.000000")
    con.execute(appt_insert, (1, 1, *first, ts, ts))
    con.execute(appt_insert, (2, 2, *second, ts, ts))
    con.commit()
    con.close()

    migrate.run_migrations()  # what the API now does on startup

    con = sqlite3.connect(db_file)
    assert "request_hash" in columns(con)
    assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0006"
    # Earliest kept, later duplicate cancelled, nothing deleted.
    assert dict(con.execute("SELECT id, status FROM appointments")) == {1: "booked", 2: "cancelled"}
    with pytest.raises(sqlite3.IntegrityError):  # and the guard is now live
        con.execute(appt_insert, (3, 2, *first, ts, ts))
    con.close()
    migrate.run_migrations()  # idempotent: a second startup is a no-op


def test_app_startup_runs_migrations_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import migrate
    from app.main import create_app

    calls: list[int] = []
    monkeypatch.setattr("app.main.run_migrations", lambda: calls.append(1))
    monkeypatch.setattr(migrate, "run_migrations", lambda: calls.append(1))
    monkeypatch.setattr(settings, "auto_migrate", False)
    with TestClient(create_app()):
        pass
    assert calls == []
    monkeypatch.setattr(settings, "auto_migrate", True)
    with TestClient(create_app()):
        pass
    assert calls == [1]
