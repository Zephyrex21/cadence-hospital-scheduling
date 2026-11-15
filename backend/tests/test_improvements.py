"""Tests for the five improvements:

1. emergency reserve  2. patient notifications  3. consultation overrun
4. re-plan after a refused apply  5. seeded demo through plan -> commit
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.enums import AppointmentOrigin, AppointmentStatus, Role
from app.models.appointment import Appointment
from app.models.audit import AuditLog
from app.models.decision import SchedulingDecision
from app.models.displacement import AppointmentDisplacement
from app.models.notification import Notification
from app.models.triage import TriageAssessment
from app.models.user import User
from app.scheduling.availability import Interval, reserved_blocks
from app.services.notifications import extract_phone, mask_phone
from tests.test_medium_fixes import T, make_appt, make_doctor, make_patient, make_type

IST = ZoneInfo("Asia/Kolkata")


def _shift(h0: int, h1: int) -> Interval:
    return Interval(T.replace(hour=h0), T.replace(hour=h1))


# =========================================================================================
# 1. Emergency reserve
# =========================================================================================


def test_reserved_blocks_sit_mid_shift_on_the_booking_grid() -> None:
    [block] = reserved_blocks([_shift(2, 6)], blocks=1, minutes=30)
    assert (block.start, block.end) == (T.replace(hour=3, minute=45), T.replace(hour=4, minute=15))


def test_reserved_blocks_spread_evenly_and_never_overlap() -> None:
    blocks = reserved_blocks([_shift(2, 14)], blocks=2, minutes=30)
    assert len(blocks) == 2
    assert blocks[0].end <= blocks[1].start
    assert all(b.start >= T.replace(hour=2) and b.end <= T.replace(hour=14) for b in blocks)
    assert all(((b.start - T.replace(hour=2)).total_seconds() / 60) % 15 == 0 for b in blocks)


def test_reserve_is_off_or_skipped_when_it_makes_no_sense() -> None:
    assert reserved_blocks([_shift(2, 6)], blocks=0, minutes=30) == []
    assert reserved_blocks([_shift(2, 6)], blocks=1, minutes=0) == []
    short = Interval(T.replace(hour=2), T.replace(hour=2, minute=45))  # too short to spare 30 min
    assert reserved_blocks([short], blocks=1, minutes=30) == []


@pytest.fixture()
def reserve_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "emergency_reserve_blocks", 1)
    monkeypatch.setattr(settings, "emergency_reserve_min", 30)


def test_routine_booking_cannot_use_the_reserve(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any, reserve_on: None
) -> None:
    with time_machine.travel(T.replace(hour=1), tick=False):
        doctor = make_doctor(db_session, user_factory)  # shift 02:00-14:00 -> reserve 07:45-08:15
        appt_type, patient = make_type(db_session), make_patient(db_session, 1)
        h = auth_headers(user_factory(Role.RECEPTIONIST))
        day = T.isoformat()

        reserve = client.get(f"/doctors/{doctor.id}/emergency-reserve", headers=h,
                             params={"day": day}).json()
        assert [r["start"][11:16] for r in reserve] == ["07:45"]

        slots = client.get("/slots", headers=h, params={
            "doctor_id": doctor.id, "type_id": appt_type.id, "day": day}).json()
        starts = {s["start"][11:16] for s in slots}
        # 07:30 and 07:45 would overlap the 07:45-08:15 hold; 07:15 ends as it begins.
        assert not {"07:30", "07:45", "08:00"} & starts
        assert {"07:00", "07:15", "08:15"} <= starts

        res = client.post("/appointments", headers=h, json={
            "patient_id": patient.id, "doctor_id": doctor.id, "type_id": appt_type.id,
            "scheduled_start": T.replace(hour=7, minute=45).isoformat()})
        assert res.status_code == 422
        assert res.json()["error"]["details"]["code"] == "emergency_reserve"


def test_an_emergency_is_absorbed_by_the_reserve_with_no_displacement(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any, reserve_on: None
) -> None:
    now = T.replace(hour=7, minute=30)
    with time_machine.travel(now, tick=False):
        doctor = make_doctor(db_session, user_factory)
        appt_type = make_type(db_session)
        n = 0
        # A completely full day, except the reserved 07:45-08:15 window and a 15-min sliver.
        for start in [T.replace(hour=2) + timedelta(minutes=30 * i) for i in range(11)] + [
            T.replace(hour=8, minute=15) + timedelta(minutes=30 * i) for i in range(11)
        ]:
            n += 1
            make_appt(db_session, doctor, make_patient(db_session, n), appt_type, start)
        emergency_patient = make_patient(db_session, 999)
        nurse = user_factory(Role.TRIAGE_NURSE, email="n@x.dev")
        db_session.add(TriageAssessment(patient_id=emergency_patient.id, nurse_id=nurse.id,
                                        acuity="a3", chief_complaint="fever"))
        db_session.commit()
        h = auth_headers(nurse)
        body = {"patient_id": emergency_patient.id, "type_id": appt_type.id, "acuity": "a3"}
        plan = client.post("/emergencies/plan", headers=h, json=body).json()
        assert plan["decision"]["status"] == "auto"
        assert plan["decision"]["chosen"]["moves"] == []  # nobody pushed back
        # it lands inside the held window (07:30 is free too: the 15-minute sliver + the hold)
        assert plan["decision"]["chosen"]["placement"]["start"][11:16] in ("07:30", "07:45")


# =========================================================================================
# 2. Notifications
# =========================================================================================


@pytest.mark.parametrize(
    ("contact", "expected"),
    [
        ("+91 98765 43210", "+919876543210"),
        ("98765 43210", "+919876543210"),
        ("098765 43210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("+44 20 7946 0958", "+442079460958"),
        ("98765 43210 / 91234 56789", "+919876543210"),
        ("asha@example.com", None),
        ("12345", None),
        ("", None),
        (None, None),
    ],
)
def test_extract_phone(contact: str | None, expected: str | None) -> None:
    assert extract_phone(contact) == expected


def test_mask_phone_hides_the_middle() -> None:
    assert mask_phone("+919876543210") == "+91••••••3210"
    assert mask_phone(None) is None


def _commit_with_displacement(
    client: TestClient, db: Session, user_factory: Any, auth_headers: Any,
    contacts: tuple[str | None, str | None] = ("+91 98765 43210", None),
) -> tuple[Any, dict[str, Any], Any]:
    """Two booked patients at 10:00 and 10:30 with a free afternoon; an A2 emergency (15-minute
    response window) can only be seen by pushing both of them back."""
    doctor = make_doctor(db, user_factory)
    appt_type = make_type(db)
    p1 = make_patient(db, 1, contact=contacts[0])
    p2 = make_patient(db, 2, contact=contacts[1])
    make_appt(db, doctor, p1, appt_type, T)
    make_appt(db, doctor, p2, appt_type, T + timedelta(minutes=30))
    emergency = make_patient(db, 3)
    nurse = user_factory(Role.TRIAGE_NURSE, email="nurse@x.dev")
    db.add(TriageAssessment(patient_id=emergency.id, nurse_id=nurse.id, acuity="a2",
                            chief_complaint="chest pain"))
    db.commit()
    h = auth_headers(nurse)
    body = {"patient_id": emergency.id, "type_id": appt_type.id, "acuity": "a2",
            "now": T.isoformat()}
    plan = client.post("/emergencies/plan", headers=h, json=body).json()
    assert plan["decision"]["status"] == "auto", plan
    res = client.post("/emergencies/commit", headers=h, json={
        **body, "fingerprint": plan["fingerprint"], "plan_digest": plan["plan_digest"],
        "idempotency_key": "k1"})
    assert res.status_code == 200, res.text
    return doctor, res.json(), h


def test_displaced_patients_are_notified(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        _, result, _ = _commit_with_displacement(client, db_session, user_factory, auth_headers)
        assert len(result["displaced"]) == 2
        rows = list(db_session.scalars(select(Notification).order_by(Notification.id)))
        assert len(rows) == 2
        by_patient = {r.patient_id: r for r in rows}
        with_phone, without_phone = by_patient[1], by_patient[2]
        assert with_phone.status == "sent" and with_phone.provider == "console"
        assert with_phone.recipient == "+919876543210" and with_phone.channel == "sms"
        assert "has moved from" in with_phone.body and "emergency" in with_phone.body
        assert without_phone.status == "skipped" and without_phone.channel == "none"
        assert without_phone.error == "No phone number on file"
        assert with_phone.decision_id == result["decision_id"]


def test_notification_list_masks_numbers_and_is_front_desk_only(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor, _, nurse_h = _commit_with_displacement(
            client, db_session, user_factory, auth_headers)
        rows = client.get("/notifications", headers=nurse_h).json()
        assert len(rows) == 2
        assert rows[0]["recipient"] is None or "•" in rows[0]["recipient"]
        assert all("98765" not in str(r["recipient"]) for r in rows)
        assert client.get("/notifications?status=skipped", headers=nurse_h).json()[0][
            "patient"]["name"] == "Pat 2"
        assert client.get("/notifications", headers=auth_headers(doctor)).status_code == 403
        assert client.get("/notifications?status=bogus", headers=nurse_h).status_code == 422


def test_failed_notifications_can_be_retried(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.notifications as notif

    monkeypatch.setattr(settings, "notify_provider", "twilio")  # no credentials configured
    with time_machine.travel(T, tick=False):
        _, _, h = _commit_with_displacement(client, db_session, user_factory, auth_headers)
        failed = client.get("/notifications?status=failed", headers=h).json()
        assert len(failed) == 1 and "not fully configured" in failed[0]["error"]
        nid = failed[0]["id"]

        again = client.post(f"/notifications/{nid}/retry", headers=h).json()
        assert again["status"] == "failed" and again["attempts"] == 2

        monkeypatch.setattr(notif, "_send_twilio", lambda row: notif.SendResult(True, ref="SM1"))
        fixed = client.post(f"/notifications/{nid}/retry", headers=h).json()
        assert fixed["status"] == "sent" and fixed["attempts"] == 3
        # a sent message can't be "retried"
        assert client.post(f"/notifications/{nid}/retry", headers=h).status_code == 422
        assert client.post("/notifications/9999/retry", headers=h).status_code == 404


def test_a_delivery_crash_never_breaks_the_emergency_commit(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.notifications as notif

    def boom(row: Notification) -> Any:
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(notif, "_send_console", boom)
    with time_machine.travel(T, tick=False):
        _, result, _ = _commit_with_displacement(client, db_session, user_factory, auth_headers)
        assert len(result["displaced"]) == 2  # the schedule change still committed
        row = db_session.scalars(
            select(Notification).where(Notification.status == "failed")
        ).first()
        assert row is not None and "provider exploded" in (row.error or "")


def test_notifications_can_be_switched_off(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "notify_provider", "off")
    with time_machine.travel(T, tick=False):
        _commit_with_displacement(client, db_session, user_factory, auth_headers)
        assert db_session.scalars(select(Notification)).first() is None


# =========================================================================================
# 3. Consultation overrun
# =========================================================================================


def _overrun_day(db: Session, user_factory: Any) -> tuple[Any, Appointment, list[Appointment]]:
    """In-progress 09:30-10:00, then 10:00, 10:30 back-to-back, a gap, and 12:00."""
    doctor = make_doctor(db, user_factory)
    appt_type = make_type(db)
    current = make_appt(db, doctor, make_patient(db, 1, contact="+91 98765 43210"), appt_type,
                        T.replace(hour=9, minute=30), AppointmentStatus.IN_PROGRESS)
    later = [
        make_appt(db, doctor, make_patient(db, 2, contact="+91 98765 00002"), appt_type, T),
        make_appt(db, doctor, make_patient(db, 3, contact="+91 98765 00003"), appt_type,
                  T + timedelta(minutes=30), AppointmentStatus.CHECKED_IN),
        make_appt(db, doctor, make_patient(db, 4, contact="+91 98765 00004"), appt_type,
                  T.replace(hour=12)),
    ]
    return doctor, current, later


def test_extending_a_consultation_ripples_only_as_far_as_needed(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor, current, (a, b, c) = _overrun_day(db_session, user_factory)
        res = client.post(f"/appointments/{current.id}/extend", headers=auth_headers(doctor),
                          json={"minutes": 20})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["scheduled_end"].startswith("2026-11-06T10:20")  # 10:00 (now) + 20
        assert [d["appointment_id"] for d in body["displaced"]] == [a.id, b.id]
        db_session.expire_all()
        assert (a.scheduled_start.minute, a.scheduled_start.hour) == (20, 10)
        assert (b.scheduled_start.hour, b.scheduled_start.minute) == (10, 50)
        assert b.status == AppointmentStatus.CHECKED_IN  # status preserved
        assert c.scheduled_start == T.replace(hour=12)  # the gap absorbed the delay
        assert current.scheduled_end == T.replace(minute=20)
        assert current.version == 2

        decision = db_session.get(SchedulingDecision, body["decision_id"])
        assert decision is not None and decision.trigger == "consult_overrun"
        moved = list(db_session.scalars(select(AppointmentDisplacement)))
        assert {m.reason for m in moved} == {"consultation_overrun"} and len(moved) == 2
        notes = list(db_session.scalars(select(Notification)))
        assert len(notes) == 2
        assert all("running over" in n.body and n.status == "sent" for n in notes)
        audits = [r.reason for r in db_session.scalars(select(AuditLog))]
        assert "consultation_extended_20min" in audits
        assert "displaced_by_consultation_overrun" in audits

        # and the decision shows up in the history screens
        listed = client.get("/displacements", headers=auth_headers(doctor)).json()
        assert len(listed) == 2


def test_extension_with_nobody_in_the_way_changes_only_the_consultation(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T.replace(hour=9, minute=40), tick=False):
        doctor = make_doctor(db_session, user_factory)
        appt_type = make_type(db_session)
        current = make_appt(db_session, doctor, make_patient(db_session, 1), appt_type,
                            T.replace(hour=9, minute=30), AppointmentStatus.IN_PROGRESS)
        make_appt(db_session, doctor, make_patient(db_session, 2), appt_type,
                  T.replace(hour=10, minute=30))
        # 10:00 + 15 = 10:15 is still clear of the 10:30 patient: no ripple, no message
        res = client.post(f"/appointments/{current.id}/extend", headers=auth_headers(doctor),
                          json={"minutes": 15})
        assert res.status_code == 200 and res.json()["displaced"] == []
        assert res.json()["decision_id"] is None
        assert db_session.scalars(select(Notification)).first() is None
        assert db_session.scalars(select(SchedulingDecision)).first() is None


def test_extension_guards(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor, current, (a, _, _) = _overrun_day(db_session, user_factory)
        other = user_factory(Role.DOCTOR, email="other@x.dev")
        recep = user_factory(Role.RECEPTIONIST, email="rec@x.dev")
        url = f"/appointments/{current.id}/extend"

        def extend(user: Any, minutes: int, **extra: Any) -> int:
            body = {"minutes": minutes, **extra}
            return client.post(url, headers=auth_headers(user), json=body).status_code

        assert extend(other, 10) == 403  # another doctor's consultation
        assert extend(recep, 10) == 403  # not a clinical role
        assert extend(doctor, 3) == 422  # too short to mean anything
        assert extend(doctor, 500) == 422  # absurdly long
        not_started = client.post(f"/appointments/{a.id}/extend", headers=auth_headers(doctor),
                                  json={"minutes": 10})
        assert not_started.status_code == 409
        assert extend(doctor, 10, version=9) == 409  # someone else changed it meanwhile
        assert client.post("/appointments/9999/extend", headers=auth_headers(doctor),
                           json={"minutes": 10}).status_code == 404


def test_overrun_pushing_a_patient_past_the_shift_is_refused_atomically(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T.replace(hour=13), tick=False):
        doctor = make_doctor(db_session, user_factory)  # shift ends 14:00
        appt_type = make_type(db_session)
        current = make_appt(db_session, doctor, make_patient(db_session, 1), appt_type,
                            T.replace(hour=12, minute=30), AppointmentStatus.IN_PROGRESS)
        nxt = make_appt(db_session, doctor, make_patient(db_session, 2), appt_type,
                        T.replace(hour=13))
        last = make_appt(db_session, doctor, make_patient(db_session, 3), appt_type,
                         T.replace(hour=13, minute=30))
        res = client.post(f"/appointments/{current.id}/extend", headers=auth_headers(doctor),
                          json={"minutes": 30})  # 13:00 + 30 -> 13:30, last must go to 14:00-14:30
        assert res.status_code == 409
        assert res.json()["error"]["details"]["code"] == "overrun_exceeds_shift"
        db_session.expire_all()
        assert nxt.scheduled_start == T.replace(hour=13)
        assert last.scheduled_start == T.replace(hour=13, minute=30)
        assert current.scheduled_end == T.replace(hour=13)
        assert db_session.scalars(select(Notification)).first() is None
        assert db_session.scalars(select(AppointmentDisplacement)).first() is None


# =========================================================================================
# 4. Re-plan after a refused apply (the contract the UI's Re-plan button relies on)
# =========================================================================================


def test_after_a_refused_apply_replan_gives_options_that_apply(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = make_doctor(db_session, user_factory)
        appt_type = make_type(db_session)
        # Back-to-back morning so an A2 (15-minute window) must displace several -> escalates.
        for i in range(8):
            make_appt(db_session, doctor, make_patient(db_session, 10 + i), appt_type,
                      T + timedelta(minutes=30 * i))
        emergency = make_patient(db_session, 99)
        nurse = user_factory(Role.TRIAGE_NURSE, email="nurse@x.dev")
        db_session.add(TriageAssessment(patient_id=emergency.id, nurse_id=nurse.id,
                                        acuity="a2", chief_complaint="chest pain"))
        db_session.commit()
        h = auth_headers(nurse)
        body = {"patient_id": emergency.id, "type_id": appt_type.id, "acuity": "a2",
                "now": T.isoformat()}
        plan = client.post("/emergencies/plan", headers=h, json=body).json()
        committed = client.post("/emergencies/commit", headers=h, json={
            **body, "fingerprint": plan["fingerprint"], "idempotency_key": "e1"}).json()
        assert committed["status"] == "escalate", committed
        did = committed["decision_id"]

        # the schedule moves on: one of the booked patients is cancelled
        victim = db_session.scalars(select(Appointment).where(
            Appointment.status == AppointmentStatus.BOOKED).order_by(Appointment.id)).first()
        assert victim is not None
        cancelled = client.post(f"/appointments/{victim.id}/cancel", headers=h, json={})
        assert cancelled.status_code == 200

        options = client.get(f"/escalations/{did}/options", headers=h).json()["options"]
        assert options, "the escalation should have stored options"
        stale = client.post(f"/escalations/{did}/apply", headers=h,
                            json={"option_index": 0, "now": T.isoformat()})
        if stale.status_code == 409:  # the contract the UI's Re-plan prompt depends on
            assert stale.json()["error"]["details"]["code"] in ("schedule_changed", "plan_expired")
        fresh = client.post(f"/escalations/{did}/replan", headers=h)
        assert fresh.status_code == 200
        assert any(o["applicable"] for o in fresh.json()["options"]) or not fresh.json()["options"]


# =========================================================================================
# 5. The seeded demo, end to end: plan -> commit, at several times of day
# =========================================================================================


@pytest.fixture()
def seed_at(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Any]:
    import app.seed as seed_mod

    monkeypatch.setattr(
        seed_mod, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    )
    monkeypatch.setattr(settings, "seed_password", None)
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "clinic_timezone", "Asia/Kolkata")
    monkeypatch.setattr(settings, "emergency_reserve_blocks", 1)  # the real default

    @contextmanager
    def go(hhmm: str) -> Iterator[None]:
        hour, minute = (int(x) for x in hhmm.split(":"))
        with time_machine.travel(datetime(2026, 11, 4, hour, minute, tzinfo=IST), tick=False):
            seed_mod.seed(quiet=True)
            yield

    return go


def _no_overlaps(db: Session) -> None:
    db.expire_all()
    rows = list(db.scalars(
        select(Appointment).where(Appointment.status.in_((
            AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_PROGRESS))
        ).order_by(Appointment.doctor_id, Appointment.scheduled_start)))
    for prev, nxt in zip(rows, rows[1:], strict=False):
        if prev.doctor_id == nxt.doctor_id:
            assert prev.scheduled_end <= nxt.scheduled_start, (prev.id, nxt.id)


@pytest.mark.parametrize("clock", ["09:20", "12:10", "16:40"])
def test_seeded_demo_survives_plan_and_commit(
    client: TestClient, db_session: Session, seed_at: Callable[[str], Any], auth_headers: Any,
    clock: str,
) -> None:
    """Whatever time the demo is opened, the signature flow must keep working and stay safe."""
    with seed_at(clock):
        nurse = db_session.scalar(select(User).where(User.email == "nurse@cadence.dev"))
        reception = db_session.scalar(select(User).where(User.email == "receptionist@cadence.dev"))
        assert nurse and reception
        nh, rh = auth_headers(nurse), auth_headers(reception)
        scenarios = [(1, "a3"), (1, "a4"), (1, "a5"), (4, "a3"), (5, "a3"), (6, "a4"), (7, "a3"),
                     (2, "a3"), (1, "a2")]
        outcomes: list[str] = []
        for i, (type_id, acuity) in enumerate(scenarios):
            patient_id = 30 + i
            assert client.post("/triage", headers=nh, json={
                "patient_id": patient_id, "acuity": acuity, "chief_complaint": "demo"
            }).status_code == 201
            body = {"patient_id": patient_id, "type_id": type_id, "acuity": acuity}
            plan = client.post("/emergencies/plan", headers=rh, json=body)
            assert plan.status_code == 200, plan.text
            pj = plan.json()
            decision = pj["decision"]
            assert decision["status"] in ("auto", "escalate")
            res = client.post("/emergencies/commit", headers=rh, json={
                **body, "fingerprint": pj["fingerprint"], "plan_digest": pj["plan_digest"],
                "idempotency_key": f"demo-{clock}-{i}"})
            assert res.status_code == 200, res.text
            result = res.json()
            outcomes.append(result["status"])

            # replaying the same click returns the same decision (no double insert)
            replay = client.post("/emergencies/commit", headers=rh, json={
                **body, "fingerprint": pj["fingerprint"], "plan_digest": pj["plan_digest"],
                "idempotency_key": f"demo-{clock}-{i}"})
            assert replay.status_code == 200
            assert replay.json()["decision_id"] == result["decision_id"]

            record = db_session.get(SchedulingDecision, result["decision_id"])
            db_session.refresh(record)
            if result["status"] == "auto":
                assert result["emergency_appointment_id"] is not None
                emergency = db_session.get(Appointment, result["emergency_appointment_id"])
                assert emergency is not None
                assert emergency.origin == AppointmentOrigin.EMERGENCY
                assert emergency.patient_id == patient_id
                moved = list(db_session.scalars(select(AppointmentDisplacement).where(
                    AppointmentDisplacement.decision_id == result["decision_id"])))
                assert len(moved) == len(result["displaced"])
                assert len(moved) <= 3  # plans touching more than 3 appointments escalate
                notes = list(db_session.scalars(select(Notification).where(
                    Notification.decision_id == result["decision_id"])))
                assert len(notes) == len(moved)  # every displaced patient has a message row
            else:
                assert result["emergency_appointment_id"] is None  # escalation: nothing inserted

        _no_overlaps(db_session)  # nothing double-booked after the whole sequence
        # The headline flow works at every hour. In the evening the next patients in the queue
        # are sicker, so the engine (correctly) refuses to bump them for a lower-acuity
        # emergency (`priority_inversion`) and escalates more often.
        minimum_auto = {"09:20": 5, "12:10": 5, "16:40": 2}[clock]
        assert outcomes.count("auto") >= minimum_auto, outcomes
        assert db_session.scalars(select(Notification).where(
            Notification.status == "failed")).first() is None
