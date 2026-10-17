"""Pure queue-logic tests: ordering by acuity, wait estimates, in-progress handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.enums import Acuity, AppointmentStatus
from app.scheduling.queue import QueueItem, compute_queue

BASE = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)


def _at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def _item(
    appt_id: int,
    start: int,
    *,
    dur: int = 30,
    doctor_id: int = 1,
    status: AppointmentStatus = AppointmentStatus.BOOKED,
    acuity: Acuity = Acuity.A5,
) -> QueueItem:
    return QueueItem(
        appointment_id=appt_id,
        doctor_id=doctor_id,
        scheduled_start=_at(start),
        scheduled_end=_at(start + dur),
        status=status,
        acuity=acuity,
    )


def test_wait_accumulates_down_a_single_doctor_queue() -> None:
    items = [_item(1, 0), _item(2, 30), _item(3, 60)]
    entries = {e.appointment_id: e for e in compute_queue(items, _at(0))}
    assert entries[1].est_wait_min == 0 and entries[1].position == 1
    assert entries[2].est_wait_min == 30 and entries[2].position == 2
    assert entries[3].est_wait_min == 60 and entries[3].position == 3


def test_higher_acuity_jumps_the_queue() -> None:
    # A2 is scheduled later than A4 but must be served first.
    items = [_item(1, 0, acuity=Acuity.A4), _item(2, 30, acuity=Acuity.A2)]
    entries = {e.appointment_id: e for e in compute_queue(items, _at(0))}
    assert entries[2].position == 1 and entries[2].est_wait_min == 0
    assert entries[1].position == 2 and entries[1].est_wait_min == 30


def test_in_progress_consult_occupies_the_doctor() -> None:
    items = [
        _item(1, 0, dur=30, status=AppointmentStatus.IN_PROGRESS),
        _item(2, 30, dur=30),
    ]
    entries = {e.appointment_id: e for e in compute_queue(items, _at(10))}
    assert entries[1].est_wait_min == 0 and entries[1].position == 1
    # Waiting patient waits until the consult's scheduled end (09:30), i.e. 20 min.
    assert entries[2].est_wait_min == 20 and entries[2].position == 2


def test_queue_is_sorted_by_acuity_across_doctors() -> None:
    items = [
        _item(1, 0, doctor_id=1, acuity=Acuity.A4),
        _item(2, 0, doctor_id=2, acuity=Acuity.A1),
    ]
    order = [e.appointment_id for e in compute_queue(items, _at(0))]
    assert order == [2, 1]  # A1 before A4


def test_completed_and_cancelled_are_excluded() -> None:
    items = [
        _item(1, 0, status=AppointmentStatus.COMPLETED),
        _item(2, 0, status=AppointmentStatus.CANCELLED),
        _item(3, 0, status=AppointmentStatus.BOOKED),
    ]
    ids = [e.appointment_id for e in compute_queue(items, _at(0))]
    assert ids == [3]
