"""Regression tests for the second review round (medium-severity fixes).

1. The demo seed leaves slack, so emergencies are usually absorbed instead of always escalating.
2. The queue and the dashboard share one definition of "waiting" (no more 50 vs 6).
3. The login throttle buckets by the REAL client IP behind trusted proxies, and cannot be
   spoofed through X-Forwarded-For when no proxy is trusted.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from app.core.clientip import client_ip
from app.core.config import settings
from app.core.enums import Acuity, AppointmentStatus, Role
from app.models.appointment import Appointment
from app.models.user import User
from app.scheduling.queue import QueueItem, compute_queue, is_here
from tests.test_medium_fixes import T, make_appt, make_doctor, make_patient, make_type

IST = ZoneInfo("Asia/Kolkata")


# --- 2. queue <-> dashboard agree --------------------------------------------------------


def test_is_here_matches_the_definition() -> None:
    now = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
    later = now + timedelta(hours=3)
    assert is_here(AppointmentStatus.CHECKED_IN, later, now)  # arrived early
    assert is_here(AppointmentStatus.BOOKED, now - timedelta(minutes=5), now)  # due / overdue
    assert not is_here(AppointmentStatus.BOOKED, later, now)  # booked for later
    assert not is_here(AppointmentStatus.IN_PROGRESS, now, now)  # being seen, not waiting


def test_queue_entries_carry_the_waiting_flag() -> None:
    now = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)

    def item(i: int, start_min: int, status: AppointmentStatus) -> QueueItem:
        s = now + timedelta(minutes=start_min)
        return QueueItem(i, 1, s, s + timedelta(minutes=15), status, Acuity.A4)

    entries = {
        e.appointment_id: e
        for e in compute_queue(
            [
                item(1, -10, AppointmentStatus.IN_PROGRESS),
                item(2, 40, AppointmentStatus.CHECKED_IN),
                item(3, -2, AppointmentStatus.BOOKED),
                item(4, 240, AppointmentStatus.BOOKED),
            ],
            now,
        )
    }
    assert [entries[i].waiting for i in (1, 2, 3, 4)] == [False, True, True, False]


def test_queue_waiting_count_equals_dashboard_total_waiting(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = make_doctor(db_session, user_factory)
        admin = user_factory(Role.ADMINISTRATOR, email="adm@x.dev")
        appt_type = make_type(db_session)
        make_appt(db_session, doctor, make_patient(db_session, 1), appt_type,
                  T - timedelta(minutes=60), AppointmentStatus.IN_PROGRESS)
        make_appt(db_session, doctor, make_patient(db_session, 2), appt_type,
                  T + timedelta(minutes=45), AppointmentStatus.CHECKED_IN)
        make_appt(db_session, doctor, make_patient(db_session, 3), appt_type,
                  T - timedelta(minutes=1))  # due now
        make_appt(db_session, doctor, make_patient(db_session, 4), appt_type,
                  T + timedelta(hours=3))  # booked for later: NOT waiting
        queue = client.get("/queue", headers=auth_headers(admin)).json()
        dash = client.get("/dashboard/summary", headers=auth_headers(admin)).json()
        assert len(queue) == 4  # the queue still lists everyone for the day ...
        assert sum(1 for e in queue if e["waiting"]) == dash["total_waiting"] == 2
        assert sum(1 for e in queue if e["status"] == "in_progress") == dash["in_progress"] == 1


# --- 3. login throttle behind proxies ---------------------------------------------------


def _request(peer: str, xff: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request(
        {"type": "http", "headers": headers, "client": (peer, 5555), "method": "POST", "path": "/"}
    )


def test_client_ip_ignores_forwarded_for_when_no_proxy_is_trusted() -> None:
    assert client_ip(_request("10.0.0.1", "6.6.6.6"), trusted_proxies=0) == "10.0.0.1"


def test_client_ip_counts_trusted_proxies_from_the_right() -> None:
    # browser -> vercel -> render: Render appended Vercel's address, Vercel appended the browser's.
    req = _request("10.0.0.1", "1.2.3.4, 76.76.21.21")
    assert client_ip(req, trusted_proxies=2) == "1.2.3.4"
    assert client_ip(req, trusted_proxies=1) == "76.76.21.21"


def test_client_ip_cannot_be_spoofed_by_prepending_entries() -> None:
    # An attacker prepends a fake address; the trusted right-hand part still wins.
    req = _request("10.0.0.1", "9.9.9.9, 1.2.3.4, 76.76.21.21")
    assert client_ip(req, trusted_proxies=2) == "1.2.3.4"


def test_client_ip_falls_back_to_the_peer_on_short_or_garbage_headers() -> None:
    assert client_ip(_request("10.0.0.1"), trusted_proxies=2) == "10.0.0.1"
    assert client_ip(_request("10.0.0.1", "1.2.3.4"), trusted_proxies=2) == "10.0.0.1"
    garbage = _request("10.0.0.1", "not-an-ip, 76.76.21.21")
    assert client_ip(garbage, trusted_proxies=2) == "10.0.0.1"


def _wrong_logins(client: TestClient, email: str, xff: str, n: int) -> None:
    for _ in range(n):
        client.post("/auth/login", json={"email": email, "password": "wrong"},
                    headers={"X-Forwarded-For": xff})


def test_behind_trusted_proxies_one_users_failures_do_not_lock_out_another(
    client: TestClient, user_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_count", 2)
    user_factory(Role.RECEPTIONIST, email="shared@x.dev")
    # Both requests arrive from the SAME proxy peer, but are different real clients.
    _wrong_logins(client, "shared@x.dev", "1.1.1.1, 76.76.21.21", 5)
    blocked = client.post("/auth/login", json={"email": "shared@x.dev", "password": "secret123"},
                          headers={"X-Forwarded-For": "1.1.1.1, 76.76.21.21"})
    assert blocked.status_code == 429  # the abuser is throttled ...
    other = client.post("/auth/login", json={"email": "shared@x.dev", "password": "secret123"},
                        headers={"X-Forwarded-For": "2.2.2.2, 76.76.21.21"})
    assert other.status_code == 200  # ... the legitimate user elsewhere is not


def test_without_trusted_proxies_a_spoofed_header_does_not_dodge_the_throttle(
    client: TestClient, user_factory: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    user_factory(Role.RECEPTIONIST, email="spoof@x.dev")
    for i in range(5):  # rotating a forged XFF each time must not reset the bucket
        _wrong_logins(client, "spoof@x.dev", f"8.8.8.{i}", 1)
    res = client.post("/auth/login", json={"email": "spoof@x.dev", "password": "secret123"},
                      headers={"X-Forwarded-For": "8.8.8.99"})
    assert res.status_code == 429


# --- 1. the demo seed leaves slack ------------------------------------------------------


@pytest.fixture()
def seed_at(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Any]:
    import app.seed as seed_mod

    monkeypatch.setattr(
        seed_mod, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    )
    monkeypatch.setattr(settings, "seed_password", None)
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "clinic_timezone", "Asia/Kolkata")

    @contextmanager
    def go(hhmm: str) -> Iterator[None]:
        hour, minute = (int(x) for x in hhmm.split(":"))
        with time_machine.travel(datetime(2026, 11, 4, hour, minute, tzinfo=IST), tick=False):
            seed_mod.seed(quiet=True)
            yield

    return go


def test_seeded_morning_schedule_is_not_back_to_back(
    db_session: Session, seed_at: Callable[[str], Any]
) -> None:
    with seed_at("09:20"):
        day = datetime(2026, 11, 4, tzinfo=IST)
        lo, noon = day.astimezone(UTC), day.replace(hour=13).astimezone(UTC)
        rows = list(db_session.scalars(
            select(Appointment).where(
                Appointment.scheduled_start >= lo, Appointment.scheduled_start < noon,
                Appointment.status != AppointmentStatus.CANCELLED,
            ).order_by(Appointment.doctor_id, Appointment.scheduled_start)
        ))
        assert rows, "the seed should create a morning schedule"
        by_doctor: dict[int, list[Appointment]] = {}
        for a in rows:
            by_doctor.setdefault(a.doctor_id, []).append(a)
        for doctor_id, appts in by_doctor.items():
            for prev, nxt in zip(appts, appts[1:], strict=False):
                gap = (nxt.scheduled_start - prev.scheduled_end).total_seconds() / 60
                assert gap >= 15, f"doctor {doctor_id}: only {gap:.0f} min between consultations"


def test_seeded_demo_lets_most_emergencies_auto_apply(
    client: TestClient, db_session: Session, seed_at: Callable[[str], Any], auth_headers: Any
) -> None:
    """The signature demo flow: a routine emergency should usually be absorbed by the slack."""
    with seed_at("09:20"):
        nurse = db_session.scalar(select(User).where(User.email == "nurse@cadence.dev"))
        reception = db_session.scalar(select(User).where(User.email == "receptionist@cadence.dev"))
        assert nurse and reception
        outcomes = []
        # (patient id, appointment type id, acuity) — A3/A4 across several specialties
        for patient_id, type_id, acuity in [(2, 1, "a3"), (3, 1, "a4"), (4, 4, "a3"), (5, 5, "a3")]:
            assert client.post("/triage", headers=auth_headers(nurse), json={
                "patient_id": patient_id, "acuity": acuity, "chief_complaint": "test"
            }).status_code == 201
            plan = client.post("/emergencies/plan", headers=auth_headers(reception), json={
                "patient_id": patient_id, "type_id": type_id, "acuity": acuity})
            assert plan.status_code == 200, plan.text
            outcomes.append(plan.json()["decision"]["status"])
        assert outcomes.count("auto") >= 3, outcomes  # was ~0 with the back-to-back seed
