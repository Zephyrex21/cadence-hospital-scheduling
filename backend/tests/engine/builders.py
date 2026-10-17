"""Pure builders for engine tests — no database, no fixtures needed.

A fixed clinic day (09:00-17:00 UTC) keeps every scenario readable: times are
expressed as minutes after 09:00 via :func:`at`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.enums import Acuity, AppointmentStatus
from app.scheduling.availability import Interval
from app.scheduling.engine import (
    EngineAppointment,
    EngineRequest,
    EngineState,
)

DAY_START = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
DAY_END = datetime(2026, 1, 5, 17, 0, tzinfo=UTC)


def at(minutes_after_9: int) -> datetime:
    """A datetime ``minutes_after_9`` minutes past 09:00 on the clinic day."""
    return DAY_START + timedelta(minutes=minutes_after_9)


def shift(doctor_id: int = 1, start: int = 0, end: int = 480) -> dict[int, tuple[Interval, ...]]:
    return {doctor_id: (Interval(at(start), at(end)),)}


def appt(
    id: int,
    start: int,
    dur: int = 30,
    *,
    doctor_id: int = 1,
    patient_id: int | None = None,
    status: AppointmentStatus = AppointmentStatus.BOOKED,
    acuity: Acuity = Acuity.A5,
    displacement_count: int = 0,
) -> EngineAppointment:
    return EngineAppointment(
        id=id,
        doctor_id=doctor_id,
        patient_id=patient_id if patient_id is not None else 1000 + id,
        start=at(start),
        end=at(start + dur),
        status=status,
        acuity=acuity,
        displacement_count=displacement_count,
    )


def state(
    appts: list[EngineAppointment],
    shifts: dict[int, tuple[Interval, ...]] | None = None,
) -> EngineState:
    return EngineState(shifts=shifts or shift(), appointments=tuple(appts))


def request(
    acuity: Acuity,
    *,
    duration_min: int = 30,
    now: int = 0,
    doctors: tuple[int, ...] = (1,),
    patient_id: int = 999,
) -> EngineRequest:
    return EngineRequest(
        patient_id=patient_id,
        acuity=acuity,
        duration_min=duration_min,
        eligible_doctor_ids=doctors,
        now=at(now),
    )


def back_to_back(count: int, dur: int = 30, *, start: int = 0, doctor_id: int = 1,
                 acuity: Acuity = Acuity.A5) -> list[EngineAppointment]:
    """A solid wall of ``count`` appointments with no gaps between them."""
    return [
        appt(i + 1, start + i * dur, dur, doctor_id=doctor_id, acuity=acuity)
        for i in range(count)
    ]
