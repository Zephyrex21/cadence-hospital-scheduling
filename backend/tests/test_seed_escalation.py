"""The seeded A1 escalation must be a *real* engine escalation.

Regression: the demo seed used to hand-write the pending escalation with placeholder
"alternatives" ({"status": "manual_review"}), which are not plans. Opening "Review options"
then crashed the API (KeyError: 'moves' -> HTTP 500 -> "Request failed" in the UI).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.decision import SchedulingDecision
from app.models.user import User

IST = ZoneInfo("Asia/Kolkata")
Headers = Callable[[User], dict[str, str]]


@pytest.fixture()
def seed_at(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Any]:
    """``with seed_at("15:10"):`` freezes the clinic clock, seeds, and stays frozen inside."""
    import app.seed as seed_mod

    monkeypatch.setattr(
        seed_mod, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    )
    monkeypatch.setattr(settings, "seed_password", None)
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "clinic_timezone", "Asia/Kolkata")

    @contextmanager
    def go(hhmm: str, *, seed: bool = True) -> Iterator[None]:
        hour, minute = (int(x) for x in hhmm.split(":"))
        with time_machine.travel(datetime(2026, 11, 4, hour, minute, tzinfo=IST), tick=False):
            if seed:
                seed_mod.seed(quiet=True)
            yield

    return go


def _admin(db: Session) -> User:
    admin = db.scalar(select(User).where(User.email == "admin@cadence.dev"))
    assert admin is not None
    return admin


def _pending(db: Session) -> SchedulingDecision:
    db.expire_all()
    rows = list(
        db.scalars(
            select(SchedulingDecision).where(
                SchedulingDecision.status == "escalated",
                SchedulingDecision.resolved_at.is_(None),
            )
        )
    )
    assert len(rows) == 1, "the demo keeps exactly one pending escalation"
    return rows[0]


@pytest.mark.parametrize("hhmm", ["03:10", "08:10", "10:10", "13:10", "15:10", "19:40", "23:10"])
def test_review_options_never_errors_at_any_time_of_day(
    client: TestClient, db_session: Session, seed_at: Any, auth_headers: Headers, hhmm: str
) -> None:
    with seed_at(hhmm):
        headers = auth_headers(_admin(db_session))
        pending = _pending(db_session)

        resp = client.get(f"/escalations/{pending.id}/options", headers=headers)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["emergency_patient"]["mrn"] == "CAD-100063"
        for option in body["options"]:  # may be empty at night: no doctor is on shift
            assert isinstance(option["moves"], list) and option["placement"]["doctor_id"]


def test_the_seeded_escalation_offers_real_options_that_can_be_applied(
    client: TestClient, db_session: Session, seed_at: Any, auth_headers: Headers
) -> None:
    with seed_at("15:10"):
        admin = _admin(db_session)
        headers = auth_headers(admin)
        pending = _pending(db_session)

        options = client.get(f"/escalations/{pending.id}/options", headers=headers).json()
        applicable = [o for o in options["options"] if o["applicable"]]
        assert applicable, "during clinic hours the engine finds at least one placement"

        applied = client.post(
            f"/escalations/{pending.id}/apply",
            json={"option_index": applicable[0]["index"], "note": "demo check"},
            headers=headers,
        )
        assert applied.status_code == 200, applied.text
        booked = db_session.scalar(
            select(Appointment).where(Appointment.patient_id == pending.patient_id)
        )
        assert booked is not None


def test_seeding_twice_keeps_a_single_pending_escalation(
    db_session: Session, seed_at: Any
) -> None:
    with seed_at("15:10"):
        first = _pending(db_session).id
        import app.seed as seed_mod

        seed_mod.seed(quiet=True)
        assert _pending(db_session).id == first


# --- data already broken in a deployed database ---------------------------------------


def _make_legacy_placeholder(db: Session, record: SchedulingDecision) -> None:
    """What the old seed wrote: no plan at all, only a label."""
    record.chosen_plan = None
    record.alternatives = [{"status": "manual_review", "label": "Clinician-directed placement"}]
    db.commit()


def test_placeholder_alternatives_do_not_crash_the_options_endpoint(
    client: TestClient, db_session: Session, seed_at: Any, auth_headers: Headers
) -> None:
    with seed_at("15:10"):
        headers = auth_headers(_admin(db_session))
        pending = _pending(db_session)
        _make_legacy_placeholder(db_session, pending)

        resp = client.get(f"/escalations/{pending.id}/options", headers=headers)

        assert resp.status_code == 200, resp.text
        assert resp.json()["options"] == []  # nothing usable, so "handle manually"


def test_reseeding_repairs_a_broken_demo_escalation(
    client: TestClient, db_session: Session, seed_at: Any, auth_headers: Headers
) -> None:
    import app.seed as seed_mod

    with seed_at("15:10"):
        headers = auth_headers(_admin(db_session))
        pending = _pending(db_session)
        assert pending.idempotency_key and pending.idempotency_key.startswith("cadence-demo-")
        _make_legacy_placeholder(db_session, pending)

        seed_mod.seed(quiet=True)  # the next Render restart

        repaired = _pending(db_session)
        resp = client.get(f"/escalations/{repaired.id}/options", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["options"], "the repaired escalation has real, reviewable options"


def test_reseeding_never_touches_a_non_demo_escalation(
    db_session: Session, seed_at: Any
) -> None:
    import app.seed as seed_mod

    with seed_at("15:10"):
        pending = _pending(db_session)
        pending.idempotency_key = "real-clinician-request-1"  # not a demo row
        _make_legacy_placeholder(db_session, pending)
        marker = pending.id

        seed_mod.seed(quiet=True)

        still = db_session.get(SchedulingDecision, marker)
        assert still is not None and still.alternatives == [
            {"status": "manual_review", "label": "Clinician-directed placement"}
        ]
