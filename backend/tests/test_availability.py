"""Pure availability-logic tests — the Phase 2 booking invariants, no database.

These assert the rules the booking service relies on: slots fit within shifts,
never overlap busy intervals, and half-open edges touch without conflicting.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.scheduling.availability import (
    Interval,
    fits_in_any,
    generate_slots,
    has_conflict,
)


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 13, hour, minute, tzinfo=UTC)


def test_touching_intervals_do_not_overlap() -> None:
    a = Interval(_at(9), _at(9, 30))
    b = Interval(_at(9, 30), _at(10))
    assert not a.overlaps(b)
    assert not b.overlaps(a)


def test_overlapping_intervals_detected() -> None:
    a = Interval(_at(9), _at(9, 30))
    b = Interval(_at(9, 15), _at(9, 45))
    assert a.overlaps(b)
    assert has_conflict(b, [a])


def test_fits_in_any_requires_full_containment() -> None:
    shift = Interval(_at(9), _at(12))
    assert fits_in_any(Interval(_at(9), _at(9, 30)), [shift])
    # Spills past the end of the shift.
    assert not fits_in_any(Interval(_at(11, 45), _at(12, 15)), [shift])
    # Starts before the shift.
    assert not fits_in_any(Interval(_at(8, 45), _at(9, 15)), [shift])


def test_generate_slots_skips_busy_and_respects_duration() -> None:
    shifts = [Interval(_at(9), _at(10))]
    busy = [Interval(_at(9), _at(9, 30))]
    slots = generate_slots(shifts, busy, duration_min=30, step_min=15)

    # Every emitted slot is 30 min, inside the shift, and conflict-free.
    for s in slots:
        assert s.end - s.start == timedelta(minutes=30)
        assert fits_in_any(s, shifts)
        assert not has_conflict(s, busy)

    starts = {s.start for s in slots}
    # 09:00 slot ends 09:30 -> overlaps the 09:00-09:30 busy block -> excluded.
    assert _at(9, 0) not in starts
    # 09:30 slot starts exactly as busy ends (half-open edges touch) -> included.
    assert _at(9, 30) in starts


def test_generate_slots_empty_when_no_shift() -> None:
    assert generate_slots([], [], duration_min=30) == []
