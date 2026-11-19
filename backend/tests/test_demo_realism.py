"""The demo must look like a working hospital on every screen, at any time of day."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import time_machine
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.enums import AppointmentOrigin, AppointmentStatus
from app.models.appointment import Appointment
from app.models.decision import SchedulingDecision
from app.models.displacement import AppointmentDisplacement
from app.models.notification import Notification
from app.models.patient import Patient
from app.services.dashboard import summary
from app.services.notifications import extract_phone

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture()
def seed_at(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Any]:
    import app.seed as seed_mod

    monkeypatch.setattr(
        seed_mod, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    )
    monkeypatch.setattr(settings, "seed_password", None)
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "clinic_timezone", "Asia/Kolkata")
    monkeypatch.setattr(settings, "emergency_reserve_blocks", 1)

    @contextmanager
    def go(hhmm: str) -> Iterator[None]:
        hour, minute = (int(x) for x in hhmm.split(":"))
        with time_machine.travel(datetime(2026, 11, 18, hour, minute, tzinfo=IST), tick=False):
            seed_mod.seed(quiet=True)
            yield

    return go


# --- people ------------------------------------------------------------------------------


def test_the_patient_population_is_large_varied_and_believable() -> None:
    import app.seed as seed_mod

    rows = seed_mod._PATIENTS
    assert len(rows) >= 200
    assert len({r[0] for r in rows}) == len(rows)  # unique MRNs
    assert len({(r[1], r[2]) for r in rows}) == len(rows)  # no identical name + birth date
    ages = [2026 - r[2].year for r in rows]
    assert sum(a < 16 for a in ages) >= 25  # a real paediatric panel
    assert sum(a >= 60 for a in ages) >= 20
    assert 0.35 <= sum(r[3] == "female" for r in rows) / len(rows) <= 0.65
    assert len({r[5] for r in rows}) >= 10  # many cities
    assert len({r[6] for r in rows}) >= 6  # many blood groups
    assert all(extract_phone(r[4]) for r in rows)  # every patient can be messaged
    assert not any("90000" in r[4] for r in rows)  # no placeholder numbers
    assert all(r[8] and len(r[8]) <= 500 for r in rows)  # a clinical note for everyone
    assert sum("Allergy:" in r[8] for r in rows) >= 20 and sum("NKDA" in r[8] for r in rows) >= 40


def test_generated_people_are_stable_between_runs() -> None:
    from app.seed_data import generate_patients

    assert generate_patients(100065, 30, set()) == generate_patients(100065, 30, set())


def test_ten_doctors_across_nine_specialties(
    db_session: Session, seed_at: Callable[[str], Any]
) -> None:
    import app.seed as seed_mod

    with seed_at("12:10"):
        assert len(seed_mod._DOCTORS) == 10
        assert len(set(seed_mod._DOCTORS.values())) == 9
        assert db_session.scalar(select(func.count()).select_from(Patient)) >= 200


# --- a busy, believable clinic -----------------------------------------------------------


@pytest.mark.parametrize("clock", ["09:20", "15:30"])
def test_every_doctor_is_busy_and_nothing_overlaps(
    db_session: Session, seed_at: Callable[[str], Any], clock: str
) -> None:
    with seed_at(clock):
        day_lo = datetime(2026, 11, 18, tzinfo=IST).astimezone(UTC)
        day_hi = datetime(2026, 11, 19, tzinfo=IST).astimezone(UTC)
        rows = list(db_session.scalars(
            select(Appointment).where(
                Appointment.scheduled_start >= day_lo, Appointment.scheduled_start < day_hi,
                Appointment.status != AppointmentStatus.CANCELLED,
            ).order_by(Appointment.doctor_id, Appointment.scheduled_start)
        ))
        per_doctor = Counter(a.doctor_id for a in rows)
        assert len(per_doctor) == 10 and min(per_doctor.values()) >= 8
        for prev, nxt in zip(rows, rows[1:], strict=False):
            if prev.doctor_id == nxt.doctor_id:
                assert prev.scheduled_end <= nxt.scheduled_start, (prev.id, nxt.id)


def test_the_dashboard_looks_alive_in_the_afternoon(
    db_session: Session, seed_at: Callable[[str], Any]
) -> None:
    with seed_at("15:30"):
        data = summary(db_session, datetime.now(UTC))
        assert data["in_progress"] >= 8  # nearly every doctor is with a patient
        assert data["total_waiting"] >= 5
        assert data["completed_today"] >= 25
        assert data["escalations_pending"] >= 1
        levels = [level for level, n in data["waiting_by_acuity"].items() if n]
        assert len(levels) >= 3, data["waiting_by_acuity"]  # a mix, not one acuity
        delays = [row["running_delay_min"] for row in data["doctor_load"]]
        assert len(delays) == 10 and any(d > 0 for d in delays)  # some run late...
        assert any(d == 0 for d in delays)  # ...and some are on time


def test_the_future_is_booked_but_still_has_free_slots(
    db_session: Session, seed_at: Callable[[str], Any]
) -> None:
    with seed_at("12:10"):
        by_day = Counter(
            a.scheduled_start.astimezone(IST).date()
            for a in db_session.scalars(select(Appointment).where(
                Appointment.status == AppointmentStatus.BOOKED))
        )
        tomorrow = datetime(2026, 11, 19, tzinfo=IST).date()
        week_out = datetime(2026, 11, 24, tzinfo=IST).date()
        assert by_day[tomorrow] >= 60  # next day is well booked ...
        assert by_day[week_out] < by_day[tomorrow]  # ... and thins out further ahead
        assert by_day[week_out] >= 15  # ... but is never empty


# --- history, decisions, messages --------------------------------------------------------


def test_a_week_of_history_is_traceable(
    db_session: Session, seed_at: Callable[[str], Any]
) -> None:
    with seed_at("12:10"):
        decisions = list(db_session.scalars(select(SchedulingDecision)))
        assert len(decisions) >= 15
        assert len({d.created_at.astimezone(IST).date() for d in decisions}) >= 6
        escalated = [d for d in decisions if d.status == "escalated"]
        assert sum(d.resolved_at is not None and bool(d.resolution_note) for d in escalated) >= 3
        assert sum(d.status == "auto_committed" for d in decisions) >= 12

        emergencies = list(db_session.scalars(select(Appointment).where(
            Appointment.origin == AppointmentOrigin.EMERGENCY)))
        assert len(emergencies) >= 10

        displacements = list(db_session.scalars(select(AppointmentDisplacement)))
        assert len(displacements) >= 6
        notified = {(n.appointment_id, n.decision_id)
                    for n in db_session.scalars(select(Notification))}
        # every displaced patient has a message, none of them failed or lack a phone
        assert all((d.appointment_id, d.decision_id) in notified for d in displacements)
        assert not list(db_session.scalars(select(Notification).where(
            Notification.status != "sent")))


def test_reseeding_changes_nothing(db_session: Session, seed_at: Callable[[str], Any]) -> None:
    import app.seed as seed_mod

    def counts() -> list[int]:
        return [
            db_session.scalar(select(func.count()).select_from(model)) or 0
            for model in (Appointment, Patient, SchedulingDecision, AppointmentDisplacement,
                          Notification)
        ]

    with seed_at("15:30"):
        before = counts()
        seed_mod.seed(quiet=True)
        seed_mod.seed(quiet=True)
        assert counts() == before
