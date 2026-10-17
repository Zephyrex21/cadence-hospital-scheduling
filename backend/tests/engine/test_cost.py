"""Unit tests for the transparent cost function."""

from __future__ import annotations

from app.core.enums import Acuity
from app.scheduling.engine.cost import (
    delay_minutes,
    fairness_factor,
    plan_cost,
    priority_factor,
)
from app.scheduling.engine.types import EngineParameters, Move
from tests.engine.builders import appt, at


def _move(appt_id: int, from_min: int, to_min: int | None, doctor_id: int = 1) -> Move:
    return Move(
        appointment_id=appt_id,
        doctor_id=doctor_id,
        from_start=at(from_min),
        to_start=at(to_min) if to_min is not None else None,
        reason="rippled_by_emergency",
    )


def test_delay_minutes_counts_the_push() -> None:
    assert delay_minutes(_move(1, 0, 30)) == 30.0


def test_delay_minutes_is_zero_when_unplaceable() -> None:
    assert delay_minutes(_move(1, 0, None)) == 0.0


def test_priority_factor_orders_by_urgency() -> None:
    # Sicker booked patients cost more to displace.
    assert priority_factor(Acuity.A2) > priority_factor(Acuity.A5)
    assert priority_factor(Acuity.A5) == 1.0
    assert priority_factor(Acuity.A2) == 4.0


def test_fairness_factor_is_convex() -> None:
    assert fairness_factor(0, base=1.0) == 1.0
    assert fairness_factor(1, base=1.0) == 2.0
    assert fairness_factor(2, base=1.0) == 4.0  # grows faster than linear


def test_plan_cost_zero_when_nothing_moves() -> None:
    assert plan_cost((), {}, EngineParameters()) == 0.0


def test_plan_cost_combines_count_delay_priority_fairness() -> None:
    params = EngineParameters()
    a = appt(1, 0, 30, acuity=Acuity.A5, displacement_count=0)
    move = _move(1, 0, 30)
    # w_count*1 (=15) + w_delay*30*priority(A5=1)*fairness(0=1) (=30) = 45
    assert plan_cost((move,), {1: a}, params) == params.w_count + 30.0


def test_prior_displacement_raises_cost() -> None:
    params = EngineParameters()
    once = appt(1, 0, 30, displacement_count=1)
    fresh = appt(2, 0, 30, displacement_count=0)
    cost_once = plan_cost((_move(1, 0, 30),), {1: once}, params)
    cost_fresh = plan_cost((_move(2, 0, 30),), {2: fresh}, params)
    assert cost_once > cost_fresh


def test_continuity_break_adds_penalty() -> None:
    params = EngineParameters()
    a = appt(1, 0, 30, doctor_id=1)
    same = plan_cost((_move(1, 0, 30, doctor_id=1),), {1: a}, params)
    moved = plan_cost((_move(1, 0, 30, doctor_id=2),), {1: a}, params)
    assert moved - same == params.w_continuity
