"""The scheduling cost function.

The cost ranks *feasible* candidate plans only. It is deliberately transparent:
every displacement contributes its delay, scaled by the displaced patient's
clinical priority and by a convex fairness penalty that grows with how many
times that appointment has already been bumped. Hard safety and fairness
constraints (see ``constraints.py``) and the escalation rules sit *above* this
function — the optimizer never gets to override them. This directly answers the
blueprint's warning that no single objective solves every fairness/safety issue.
"""

from __future__ import annotations

from app.core.enums import Acuity
from app.scheduling.engine.types import (
    ACUITY_LEVEL,
    EngineAppointment,
    EngineParameters,
    Move,
)


def delay_minutes(move: Move) -> float:
    """Minutes an appointment is pushed later. 0 when it cannot be placed."""
    if move.to_start is None:
        return 0.0
    return (move.to_start - move.from_start).total_seconds() / 60.0


def priority_factor(acuity: Acuity) -> float:
    """Displacing a higher-priority booked patient costs more.

    A2 (level 2) -> 4x, ... A5 (level 5) -> 1x. Routine patients are the
    cheapest to move, sicker booked patients the most expensive.
    """
    return float(6 - ACUITY_LEVEL[acuity])


def fairness_factor(displacement_count: int, base: float) -> float:
    """Convex penalty: re-displacing an already-bumped patient is expensive, so
    the engine naturally spreads displacement load across patients."""
    return (1.0 + base) ** displacement_count


def plan_cost(
    moves: tuple[Move, ...],
    displaced: dict[int, EngineAppointment],
    params: EngineParameters,
) -> float:
    """Total cost of a candidate's displacements. Zero when nothing moves."""
    total = params.w_count * len(moves)
    for move in moves:
        appt = displaced[move.appointment_id]
        total += (
            params.w_delay
            * delay_minutes(move)
            * priority_factor(appt.acuity)
            * fairness_factor(appt.displacement_count, params.w_fairness_base)
        )
        if move.doctor_id != appt.doctor_id:
            total += params.w_continuity  # moved to a different doctor (continuity break)
    return total
