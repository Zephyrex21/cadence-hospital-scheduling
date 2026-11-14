"""Pure patient-queue logic (no database access).

Builds a priority-ordered waiting list with waiting-time estimates. Kept pure so
the ordering and estimate rules are unit-testable in isolation.

Ordering (per the blueprint): most-urgent acuity first, then by scheduled time.
The estimate is a transparent heuristic — a patient waits for the current
consultation to finish plus the expected durations of everyone ahead of them in
their doctor's queue. It is explicitly an operational estimate, not a promise.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from app.core.enums import Acuity, AppointmentStatus
from app.scheduling.engine import ACUITY_LEVEL

_WAITING = (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN)


def is_here(status: AppointmentStatus, scheduled_start: datetime, now: datetime) -> bool:
    """Is this patient actually *waiting* right now?

    True once they are checked in, or a booked appointment's time has come — not merely
    because they are booked for later today. This single definition is shared by the queue
    and the dashboard tiles so the two screens can never disagree.
    """
    if status == AppointmentStatus.CHECKED_IN:
        return True
    return status == AppointmentStatus.BOOKED and scheduled_start <= now


@dataclass(frozen=True)
class QueueItem:
    appointment_id: int
    doctor_id: int
    scheduled_start: datetime
    scheduled_end: datetime
    status: AppointmentStatus
    acuity: Acuity


@dataclass(frozen=True)
class QueueEntry:
    appointment_id: int
    doctor_id: int
    acuity: Acuity
    status: AppointmentStatus
    scheduled_start: datetime
    est_wait_min: int
    position: int  # 1-based position within the doctor's queue
    waiting: bool = False  # actually here / due now (see ``is_here``); False = booked for later


def _duration_min(item: QueueItem) -> float:
    return (item.scheduled_end - item.scheduled_start).total_seconds() / 60.0


def compute_queue(items: list[QueueItem], now: datetime) -> list[QueueEntry]:
    """Order the active waiting list and estimate each patient's wait.

    Within a doctor: the in-progress consultation (if any) occupies the doctor
    until its scheduled end; waiting patients are then served by acuity, then by
    scheduled time. Across doctors, the returned list is sorted by acuity then
    scheduled time for a single triage-style view.
    """
    by_doctor: dict[int, list[QueueItem]] = defaultdict(list)
    for item in items:
        by_doctor[item.doctor_id].append(item)

    entries: list[QueueEntry] = []
    for doctor_id, group in by_doctor.items():
        pending = [g for g in group if g.status in _WAITING]

        def priority(g: QueueItem) -> tuple[int, datetime, int]:
            return (ACUITY_LEVEL[g.acuity], g.scheduled_start, g.appointment_id)

        cursor = now
        position = 0
        for ip in sorted(
            (g for g in group if g.status == AppointmentStatus.IN_PROGRESS),
            key=lambda g: g.scheduled_start,
        ):
            position += 1
            entries.append(
                QueueEntry(ip.appointment_id, doctor_id, ip.acuity, ip.status,
                           ip.scheduled_start, 0, position)
            )
            # The protected consult runs at least until its scheduled end.
            cursor = max(cursor, ip.scheduled_end)

        # Simulate the doctor's day. Someone is only served once they are actually *here*:
        # checked in, or their appointment time has come. If nobody is, the doctor is idle
        # until the next booked time (so a patient booked for 15:00 is not "next in line" at 09:00).
        while pending:
            here = [g for g in pending if g.status == AppointmentStatus.CHECKED_IN
                    or g.scheduled_start <= cursor]
            if not here:
                cursor = min(g.scheduled_start for g in pending)
                continue
            nxt = min(here, key=priority)
            pending.remove(nxt)
            position += 1
            wait = max(0, round((cursor - now).total_seconds() / 60.0))
            entries.append(
                QueueEntry(nxt.appointment_id, doctor_id, nxt.acuity, nxt.status,
                           nxt.scheduled_start, wait, position,
                           waiting=is_here(nxt.status, nxt.scheduled_start, now))
            )
            cursor = cursor + (nxt.scheduled_end - nxt.scheduled_start)
    entries.sort(key=lambda e: (ACUITY_LEVEL[e.acuity], e.scheduled_start, e.appointment_id))
    return entries
