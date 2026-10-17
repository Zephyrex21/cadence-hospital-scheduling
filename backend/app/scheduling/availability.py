"""Pure scheduling-availability helpers (no database access).

These functions encode the Phase 2 booking rules — an appointment must fall
entirely within a doctor's shift and must not overlap another active appointment.
Keeping them pure makes the invariants unit-testable in isolation and lets the
scheduling engine (later phases) reuse the exact same gap/overlap logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def overlaps(self, other: Interval) -> bool:
        # Half-open intervals [start, end): touching edges do NOT overlap.
        return self.start < other.end and other.start < self.end

    def contains(self, other: Interval) -> bool:
        return self.start <= other.start and other.end <= self.end


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
    step_min: int = 15,
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
