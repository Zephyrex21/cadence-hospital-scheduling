"""Pure scheduling-availability helpers (no database access).

These functions encode the Phase 2 booking rules — an appointment must fall
entirely within a doctor's shift and must not overlap another active appointment.
Keeping them pure makes the invariants unit-testable in isolation and lets the
scheduling engine (later phases) reuse the exact same gap/overlap logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

SLOT_STEP_MIN = 15  # bookable start times fall on this grid, aligned to each shift's start


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def overlaps(self, other: Interval) -> bool:
        # Half-open intervals [start, end): touching edges do NOT overlap.
        return self.start < other.end and other.start < self.end

    def contains(self, other: Interval) -> bool:
        return self.start <= other.start and other.end <= self.end


def reserved_blocks(
    shifts: list[Interval], blocks: int, minutes: int, step_min: int = SLOT_STEP_MIN
) -> list[Interval]:
    """Emergency-reserve windows: ``blocks`` evenly spaced ``minutes``-long holds per shift.

    Routine bookings may not use them; only the emergency engine can. Block *k* is centred at
    k/(blocks+1) of the shift and snapped to the booking grid, so the holds are predictable
    (a 09:00-13:00 shift with one 30-minute block holds 10:45-11:15). Shifts too short to spare
    the time are left alone.
    """
    if blocks <= 0 or minutes <= 0:
        return []
    held: list[Interval] = []
    for shift in sorted(shifts, key=lambda s: s.start):
        length_min = (shift.end - shift.start).total_seconds() / 60
        if length_min < minutes * 2:
            continue
        latest = int((length_min - minutes) // step_min) * step_min
        for k in range(1, blocks + 1):
            centre = length_min * k / (blocks + 1)
            offset = min(max(round((centre - minutes / 2) / step_min) * step_min, 0), latest)
            start = shift.start + timedelta(minutes=offset)
            block = Interval(start, start + timedelta(minutes=minutes))
            if not any(block.overlaps(h) for h in held):
                held.append(block)
    return held


def has_conflict(candidate: Interval, busy: list[Interval]) -> bool:
    """True if ``candidate`` overlaps any busy interval."""
    return any(candidate.overlaps(b) for b in busy)


def fits_in_any(candidate: Interval, shifts: list[Interval]) -> bool:
    """True if ``candidate`` lies entirely within at least one shift."""
    return any(shift.contains(candidate) for shift in shifts)


def generate_slots(
    shifts: list[Interval],
    busy: list[Interval],
    duration_min: int,
    step_min: int = SLOT_STEP_MIN,
) -> list[Interval]:
    """Enumerate conflict-free candidate slots of ``duration_min`` within shifts.

    Slots are stepped on a ``step_min`` grid aligned to each shift's start. A slot
    is emitted only when it fits inside the shift and overlaps no busy interval.
    """
    duration = timedelta(minutes=duration_min)
    step = timedelta(minutes=step_min)
    slots: list[Interval] = []
    for shift in sorted(shifts, key=lambda s: s.start):
        cursor = shift.start
        while cursor + duration <= shift.end:
            candidate = Interval(cursor, cursor + duration)
            if not has_conflict(candidate, busy):
                slots.append(candidate)
            cursor += step
    return slots
