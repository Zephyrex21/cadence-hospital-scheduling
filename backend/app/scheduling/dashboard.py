"""Pure dashboard logic (no database access).

The only non-trivial computation is a doctor's *running delay* — a transparent
estimate of how far behind they are right now. Kept pure so it is unit-testable.
"""

from __future__ import annotations

from datetime import datetime

from app.core.enums import AppointmentStatus
from app.scheduling.queue import QueueItem

_WAITING = (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN)


def doctor_running_delay(items: list[QueueItem], now: datetime) -> int:
    """Minutes the doctor is running behind, 0 if on time.

    Two signals, whichever is larger:
      * an in-progress consultation that has overrun its scheduled end;
      * the oldest waiting patient whose scheduled start is already in the past.
    """
    candidates: list[datetime] = []

    overrunning = [
        i
        for i in items
        if i.status == AppointmentStatus.IN_PROGRESS and i.scheduled_end < now
    ]
    if overrunning:
        candidates.append(min(i.scheduled_end for i in overrunning))

    overdue = [i for i in items if i.status in _WAITING and i.scheduled_start < now]
    if overdue:
        candidates.append(min(i.scheduled_start for i in overdue))

    if not candidates:
        return 0
    behind = now - min(candidates)
    return max(0, round(behind.total_seconds() / 60.0))
