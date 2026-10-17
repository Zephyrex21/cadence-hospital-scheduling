"""Pure unit tests for the constraint/escalation predicates.

These exercise ``candidate_rejections`` and ``escalation_reasons`` directly, so
each hard safety/fairness rule is pinned in isolation — independent of the
engine's candidate-generation and ranking.
"""

from __future__ import annotations

from app.core.enums import Acuity, AppointmentStatus
from app.scheduling.availability import Interval
from app.scheduling.engine.constraints import candidate_rejections, escalation_reasons
from app.scheduling.engine.types import (
    CandidatePlan,
    EngineAppointment,
    EngineParameters,
    Move,
    Placement,
)
from tests.engine.builders import appt, at, request

DAY_SHIFT: tuple[Interval, ...] = (Interval(at(0), at(480)),)


def _reject(
    placement: Placement,
    moves: tuple[Move, ...] = (),
    *,
    acuity: Acuity = Acuity.A3,
    now: int = 0,
    displaced: dict[int, EngineAppointment] | None = None,
    survivors: tuple[Interval, ...] = (),
    shifts: tuple[Interval, ...] = DAY_SHIFT,
    params: EngineParameters | None = None,
    enforce_window: bool = True,
    patient_busy: dict[int, tuple[Interval, ...]] | None = None,
) -> tuple[str, ...]:
    return candidate_rejections(
        placement,
        moves,
        request(acuity, now=now),
        displaced or {},
        list(survivors),
        shifts,
        params or EngineParameters(),
        enforce_window=enforce_window,
        patient_busy=patient_busy,
    )


def _move(appt_id: int, to_min: int | None, doctor_id: int = 1) -> Move:
    return Move(appt_id, doctor_id, at(0), at(to_min) if to_min is not None else None, "x")


def test_clean_placement_has_no_rejections() -> None:
    assert _reject(Placement(1, at(30), at(60))) == ()


def test_placement_outside_availability_rejected() -> None:
    assert "placement_outside_availability" in _reject(Placement(1, at(500), at(530)))


def test_response_window_is_hard_and_can_be_disabled() -> None:
    late = Placement(1, at(30), at(60))  # A2 window is 15 min
    assert "misses_response_window" in _reject(late, acuity=Acuity.A2, now=0)
    # Disabling the window (the A1 path) removes the only objection.
    assert _reject(late, acuity=Acuity.A2, now=0, enforce_window=False) == ()


def test_survivor_conflict_rejected() -> None:
    r = _reject(Placement(1, at(0), at(30)), survivors=(Interval(at(15), at(45)),))
    assert "placement_conflicts_with_survivor" in r


def test_in_progress_consultation_cannot_be_displaced() -> None:
    protected = appt(1, 0, 30, status=AppointmentStatus.IN_PROGRESS)
    r = _reject(Placement(1, at(60), at(90)), (_move(1, 300),), displaced={1: protected})
    assert "would_interrupt_in_progress:1" in r


def test_displaced_overflow_rejected() -> None:
    r = _reject(
        Placement(1, at(60), at(90)), (_move(1, None),), displaced={1: appt(1, 0, 30)}
    )
    assert "displaced_overflow:1" in r


def test_fairness_cap_rejected_in_isolation() -> None:
    capped = appt(1, 0, 30, displacement_count=2)  # cap defaults to 2
    r = _reject(Placement(1, at(60), at(90)), (_move(1, 300),), displaced={1: capped})
    assert "exceeds_displacement_cap:1" in r


def test_priority_inversion_rejected() -> None:
    sicker = appt(1, 0, 30, acuity=Acuity.A2)
    r = _reject(
        Placement(1, at(60), at(90)),
        (_move(1, 300),),
        displaced={1: sicker},
        acuity=Acuity.A4,  # less urgent than the A2 it would bump
    )
    assert "priority_inversion:1" in r


def test_emergency_patient_double_booked_rejected() -> None:
    # The emergency patient (id 999) is already booked elsewhere 09:30–10:00.
    busy = {999: (Interval(at(30), at(60)),)}
    r = _reject(Placement(1, at(30), at(60)), patient_busy=busy)
    assert "patient_double_booked" in r


def test_displaced_patient_double_booked_rejected() -> None:
    # Appointment 1 belongs to patient 42; rippling it to 09:60 collides with
    # that patient's own appointment elsewhere.
    moved = appt(1, 0, 30, patient_id=42)
    busy = {42: (Interval(at(60), at(90)),)}
    r = _reject(
        Placement(1, at(0), at(30)),
        (_move(1, 60),),
        displaced={1: moved},
        patient_busy=busy,
    )
    assert "patient_double_booked:1" in r


def _plan(moves: tuple[Move, ...] = (), cost: float = 0.0) -> CandidatePlan:
    return CandidatePlan(Placement(1, at(0), at(30)), moves, cost, True, ())


def test_escalation_too_many_displacements() -> None:
    moves = tuple(_move(i, 30) for i in range(2))
    r = escalation_reasons(
        _plan(moves), request(Acuity.A2), EngineParameters(max_auto_displaced=1)
    )
    assert "too_many_displacements" in r


def test_escalation_cost_over_threshold() -> None:
    r = escalation_reasons(
        _plan(cost=2000.0), request(Acuity.A2), EngineParameters(escalation_cost_threshold=1000.0)
    )
    assert "cost_over_threshold" in r


def test_escalation_delay_over_auto_limit() -> None:
    r = escalation_reasons(
        _plan((_move(1, 60),)), request(Acuity.A2), EngineParameters(max_auto_delay_min=30)
    )
    assert "delay_over_auto_limit" in r


def test_escalation_clean_plan_has_no_reasons() -> None:
    assert escalation_reasons(_plan(), request(Acuity.A2), EngineParameters()) == ()
