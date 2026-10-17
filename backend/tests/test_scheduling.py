"""Booking/cancel API tests: availability, no-double-book, RBAC, cancellation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models.appointment_type import AppointmentType
from app.models.doctor import DoctorProfile
from app.models.patient import Patient
from app.models.shift import Shift
from app.models.user import User


def _at(hour: int, minute: int = 0) -> datetime:
    """A fixed UTC instant *tomorrow* at the given time.

    Booking now rejects past times and the slots endpoint hides past slots, so
    tests anchor to a day that is always in the future regardless of the wall
    clock when the suite runs (avoids time-of-day flakiness).
    """
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, tzinfo=UTC)


@pytest.fixture()
def scheduling_setup(
    db_session: Session, user_factory: Callable[..., User]
) -> dict[str, int]:
    """A doctor with a 09:00–12:00 shift, a 30-min type, and one patient."""
    doctor = user_factory(Role.DOCTOR, email="doc@cadence.dev")
    db_session.add(DoctorProfile(user_id=doctor.id, specialty="general"))
    db_session.add(Shift(doctor_id=doctor.id, start_utc=_at(9), end_utc=_at(12)))
    appt_type = AppointmentType(name="General", default_duration_min=30, specialty="general")
    patient = Patient(
        mrn="CAD-900001", name="Test Patient", date_of_birth=date(1990, 1, 1), sex="other"
    )
    db_session.add_all([appt_type, patient])
    db_session.commit()
    return {"doctor_id": doctor.id, "type_id": appt_type.id, "patient_id": patient.id}


def _book(client, headers, setup, hour, minute=0):  # type: ignore[no-untyped-def]
    return client.post(
        "/appointments",
        headers=headers,
        json={
            "patient_id": setup["patient_id"],
            "doctor_id": setup["doctor_id"],
            "type_id": setup["type_id"],
            "scheduled_start": _at(hour, minute).isoformat(),
        },
    )


def test_receptionist_can_book_within_availability(
    client: TestClient,
    scheduling_setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    resp = _book(client, headers, scheduling_setup, 9, 30)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "booked"
    assert body["patient"]["mrn"] == "CAD-900001"


def test_cannot_double_book_overlapping_slot(
    client: TestClient,
    scheduling_setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    assert _book(client, headers, scheduling_setup, 9, 0).status_code == 201
    # 09:15 overlaps the 09:00–09:30 booking.
    clash = _book(client, headers, scheduling_setup, 9, 15)
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "conflict"


def test_adjacent_slot_is_allowed(
    client: TestClient,
    scheduling_setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    assert _book(client, headers, scheduling_setup, 9, 0).status_code == 201
    # 09:30 starts exactly when the first ends — no overlap.
    assert _book(client, headers, scheduling_setup, 9, 30).status_code == 201


def test_cannot_book_outside_availability(
    client: TestClient,
    scheduling_setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    # 13:00 is outside the 09:00–12:00 shift.
    resp = _book(client, headers, scheduling_setup, 13, 0)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_doctor_cannot_book(
    client: TestClient,
    scheduling_setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.DOCTOR, email="other-doc@cadence.dev"))
    assert _book(client, headers, scheduling_setup, 10, 0).status_code == 403


def test_cancel_frees_the_slot(
    client: TestClient,
    scheduling_setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    booked = _book(client, headers, scheduling_setup, 9, 0)
    appt_id = booked.json()["id"]

    cancelled = client.post(f"/appointments/{appt_id}/cancel", headers=headers, json={})
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # The slot is reusable now that the first booking is cancelled.
    assert _book(client, headers, scheduling_setup, 9, 0).status_code == 201


def test_slots_endpoint_excludes_booked_time(
    client: TestClient,
    scheduling_setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    _book(client, headers, scheduling_setup, 9, 0)
    resp = client.get(
        "/slots",
        headers=headers,
        params={
            "doctor_id": scheduling_setup["doctor_id"],
            "type_id": scheduling_setup["type_id"],
            "day": _at(9).isoformat(),
        },
    )
    assert resp.status_code == 200
    # Compare parsed instants, not raw strings: the API emits RFC-3339 "Z" while
    # datetime.isoformat() emits "+00:00" — the same instant, different spelling.
    starts = {datetime.fromisoformat(s["start"]) for s in resp.json()}
    assert _at(9, 0) not in starts
    assert _at(9, 30) in starts


# --- booking integrity (A5) --------------------------------------------------


def test_cannot_book_in_the_past(
    client: TestClient,
    scheduling_setup: dict[str, int],
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    past = datetime.now(UTC) - timedelta(hours=1)
    resp = client.post(
        "/appointments",
        headers=headers,
        json={
            "patient_id": scheduling_setup["patient_id"],
            "doctor_id": scheduling_setup["doctor_id"],
            "type_id": scheduling_setup["type_id"],
            "scheduled_start": past.isoformat(),
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["code"] == "past_time"


def test_cannot_book_patient_into_overlapping_appointment(
    client: TestClient,
    scheduling_setup: dict[str, int],
    db_session: Session,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    headers = auth_headers(user_factory(Role.RECEPTIONIST))
    # First booking with the setup doctor at 09:00.
    assert _book(client, headers, scheduling_setup, 9, 0).status_code == 201

    # A second doctor, free at the same time.
    other = user_factory(Role.DOCTOR, email="overlap-doc@cadence.dev")
    db_session.add(DoctorProfile(user_id=other.id, specialty="general"))
    db_session.add(Shift(doctor_id=other.id, start_utc=_at(9), end_utc=_at(12)))
    db_session.commit()

    # Same patient, different doctor, overlapping 09:15 — the patient can't be
    # in two places at once.
    clash = client.post(
        "/appointments",
        headers=headers,
        json={
            "patient_id": scheduling_setup["patient_id"],
            "doctor_id": other.id,
            "type_id": scheduling_setup["type_id"],
            "scheduled_start": _at(9, 15).isoformat(),
        },
    )
    assert clash.status_code == 409
    assert clash.json()["error"]["details"]["code"] == "patient_overlap"


def test_slots_endpoint_excludes_past_slots(
    client: TestClient,
    db_session: Session,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    doctor = user_factory(Role.DOCTOR, email="pastslot-doc@cadence.dev")
    db_session.add(DoctorProfile(user_id=doctor.id, specialty="general"))
    now = datetime.now(UTC)
    # A shift straddling "now": the first half is already in the past.
    db_session.add(
        Shift(
            doctor_id=doctor.id,
            start_utc=now - timedelta(hours=1),
            end_utc=now + timedelta(hours=1),
        )
    )
    appt_type = AppointmentType(name="General", default_duration_min=30, specialty="general")
    db_session.add(appt_type)
    db_session.commit()

    headers = auth_headers(user_factory(Role.RECEPTIONIST, email="r-pastslot@cadence.dev"))
    resp = client.get(
        "/slots",
        headers=headers,
        params={"doctor_id": doctor.id, "type_id": appt_type.id, "day": now.isoformat()},
    )
    assert resp.status_code == 200
    starts = [datetime.fromisoformat(s["start"]) for s in resp.json()]
    assert starts, "future slots in the next hour should still be offered"
    assert all(s >= now for s in starts), "no slot may start in the past"
