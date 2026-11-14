"""Regression tests for the low-severity review round."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.schemas.patient import check_contact
from tests.test_medium_fixes import T, make_appt, make_doctor, make_patient, make_type

BASE = {"name": "Asha Rao", "date_of_birth": "1990-01-01", "sex": "female"}


# --- 4. contact validation -----------------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["+91 98765 43210", "555-0101", "(011) 2345 6789", "asha@example.com", "98765 43210"]
)
def test_valid_contacts_are_accepted(value: str) -> None:
    assert check_contact(value) == value


@pytest.mark.parametrize("value", ["abc", "12", "call me", "a@b", "+++", "1234567890123456789"])
def test_junk_contacts_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        check_contact(value)


def test_api_rejects_a_junk_contact_but_allows_blank(
    client: TestClient, user_factory: Any, auth_headers: Any
) -> None:
    h = auth_headers(user_factory(Role.RECEPTIONIST))
    assert client.post("/patients", headers=h, json={**BASE, "contact": "abc"}).status_code == 422
    assert client.post("/patients", headers=h, json={**BASE, "contact": "  "}).status_code == 201


# --- 5. duplicate patients -------------------------------------------------------------------


def test_registering_the_same_person_twice_needs_confirmation(
    client: TestClient, user_factory: Any, auth_headers: Any
) -> None:
    h = auth_headers(user_factory(Role.RECEPTIONIST))
    first = client.post("/patients", headers=h, json=BASE)
    assert first.status_code == 201
    dup = client.post("/patients", headers=h, json={**BASE, "name": "  asha   RAO "})
    assert dup.status_code == 409
    err = dup.json()["error"]
    assert err["details"]["code"] == "possible_duplicate"
    assert err["details"]["matches"][0]["mrn"] == first.json()["mrn"]
    # confirmed -> allowed; a different date of birth is simply a different person
    assert client.post("/patients", headers=h,
                       json={**BASE, "allow_duplicate": True}).status_code == 201
    assert client.post("/patients", headers=h,
                       json={**BASE, "date_of_birth": "1991-01-01"}).status_code == 201


# --- 6 + 9. booking: timezone required, grid enforced -------------------------------------------


def _book(client: TestClient, h: Any, doctor: Any, patient: Any, appt_type: Any, start: str) -> Any:
    return client.post("/appointments", headers=h, json={
        "patient_id": patient.id, "doctor_id": doctor.id, "type_id": appt_type.id,
        "scheduled_start": start})


def test_booking_requires_a_timezone_and_a_real_slot(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = make_doctor(db_session, user_factory)  # shift 02:00-14:00 UTC
        appt_type, patient = make_type(db_session), make_patient(db_session, 1)
        h = auth_headers(user_factory(Role.RECEPTIONIST))

        naive = _book(client, h, doctor, patient, appt_type, "2026-11-06T11:00:00")
        assert naive.status_code == 422
        assert "timezone" in naive.json()["error"]["message"]

        off = _book(client, h, doctor, patient, appt_type, "2026-11-06T11:07:00Z")
        assert off.status_code == 422
        assert off.json()["error"]["details"] and "15 minutes" in off.json()["error"]["message"]

        ok = _book(client, h, doctor, patient, appt_type, "2026-11-06T11:15:00Z")
        assert ok.status_code == 201
        # an offset-style timestamp for the same instant is fine too
        other = make_patient(db_session, 2)
        assert _book(client, h, doctor, other, appt_type,
                     "2026-11-06T17:15:00+05:30").status_code == 201


# --- 7. one error envelope -------------------------------------------------------------------


def test_validation_errors_use_the_standard_envelope_and_list_every_problem(
    client: TestClient, user_factory: Any, auth_headers: Any
) -> None:
    h = auth_headers(user_factory(Role.RECEPTIONIST))
    res = client.post("/patients", headers=h,
                      json={"name": "A", "date_of_birth": "2999-01-01", "sex": "x",
                            "contact": "abc"})
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "validation_error" and "detail" not in res.json()
    fields = {d["field"] for d in err["details"]}
    assert {"name", "date_of_birth", "sex", "contact"} <= fields
    assert err["message"].count(";") == 2 and "(+1 more)" in err["message"]
    assert "Value error," not in err["message"]


# --- 10. no-show only once the appointment time has come --------------------------------------


def test_cannot_mark_a_future_appointment_as_no_show(
    client: TestClient, db_session: Session, user_factory: Any, auth_headers: Any
) -> None:
    with time_machine.travel(T, tick=False):
        doctor = make_doctor(db_session, user_factory)
        appt_type = make_type(db_session)
        later = make_appt(db_session, doctor, make_patient(db_session, 1), appt_type,
                          T + timedelta(hours=2))
        past = make_appt(db_session, doctor, make_patient(db_session, 2), appt_type,
                         T - timedelta(hours=1))
        admin = auth_headers(user_factory(Role.ADMINISTRATOR))
        early = client.post(f"/appointments/{later.id}/status", headers=admin,
                            json={"action": "no_show"})
        assert early.status_code == 409 and early.json()["error"]["details"]["code"] == "too_early"
        assert client.post(f"/appointments/{past.id}/status", headers=admin,
                           json={"action": "no_show"}).status_code == 200


# --- 11. security headers --------------------------------------------------------------------


def test_api_sends_security_headers(client: TestClient) -> None:
    res = client.get("/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"] == "no-referrer"
    assert res.headers["cache-control"] == "no-store"
    assert "permissions-policy" in res.headers
