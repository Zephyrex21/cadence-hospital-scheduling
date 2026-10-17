"""Hard constraints and escalation checks.

Two distinct gates:

* ``candidate_rejections`` returns the reasons a candidate plan is *infeasible*
  (it must never be committed). These encode clinical safety and the fairness
  cap, and sit above the cost function.
* ``escalation_reasons`` returns why an otherwise-feasible best plan must still
  be handed to a human instead of auto-committing (A1, large blast radius,
  cost over threshold).

Keeping these as pure predicate functions makes each invariant independently
testable and keeps the engine's control flow readable.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from app.scheduling.availability import Interval, has_conflict
from app.scheduling.engine.cost import delay_minutes
from app.scheduling.engine.types import (
    ACUITY_LEVEL,
    CandidatePlan,
    EngineAppointment,
    EngineParameters,
    EngineRequest,
    Move,
    Placement,
)


def _doctor_shift_intervals(shifts: tuple[Interval, ...], iv: Interval) -> bool:
    return any(s.contains(iv) for s in shifts)


def candidate_rejections(
    placement: Placement,
    moves: tuple[Move, ...],
    request: EngineRequest,
    displaced: dict[int, EngineAppointment],
    survivors_busy: list[Interval],
    doctor_shifts: tuple[Interval, ...],
    params: EngineParameters,
    *,
    enforce_window: bool = True,
    patient_busy: Mapping[int, tuple[Interval, ...]] | None = None,
) -> tuple[str, ...]:
    """All reasons this candidate is infeasible (empty tuple == feasible)."""
    reasons: list[str] = []
    placed = Interval(placement.start, placement.end)
    patient_busy = patient_busy or {}

    # 1. The emergency must fit within the doctor's availability.
    if not _doctor_shift_intervals(doctor_shifts, placed):
        reasons.append("placement_outside_availability")

    # 2. The placement must meet the acuity's clinical response-time target.
    #    (Hard for A2-A5; skipped for A1, which is always escalated with options.)
    if enforce_window:
        window = params.response_window_min[request.acuity]
        if placement.start > request.now + timedelta(minutes=window):
            reasons.append("misses_response_window")

    # 3. The emergency must not collide with any appointment that stays put.
    if has_conflict(placed, survivors_busy):
        reasons.append("placement_conflicts_with_survivor")

    # 3b. The emergency patient must not already be booked elsewhere at this time.
    if has_conflict(placed, list(patient_busy.get(request.patient_id, ()))):
        reasons.append("patient_double_booked")

    for move in moves:
        appt = displaced[move.appointment_id]

        # 4. In-progress consultations are never displaced.
        if appt.is_protected:
            reasons.append(f"would_interrupt_in_progress:{appt.id}")

        # 5. Every displaced appointment must land somewhere valid.
        if move.to_start is None:
            reasons.append(f"displaced_overflow:{appt.id}")
            continue

        # 5b. A displaced appointment's new slot must not collide with that
        #     patient's own other appointments elsewhere.
        moved_iv = Interval(move.to_start, move.to_start + appt.duration)
        if has_conflict(moved_iv, list(patient_busy.get(appt.patient_id, ()))):
            reasons.append(f"patient_double_booked:{appt.id}")

        # 6. Fairness cap: never bump an appointment past the hard limit.
        if appt.displacement_count + 1 > params.max_displacements:
            reasons.append(f"exceeds_displacement_cap:{appt.id}")

        # 7. Priority-inversion guard: a less-urgent arrival may not displace a
        #    strictly more-urgent booked patient.
        if ACUITY_LEVEL[request.acuity] > ACUITY_LEVEL[appt.acuity]:
            reasons.append(f"priority_inversion:{appt.id}")

    return tuple(reasons)


def escalation_reasons(
    plan: CandidatePlan,
    request: EngineRequest,
    params: EngineParameters,
) -> tuple[str, ...]:
    """Why a feasible best plan must still go to a human (empty == auto-commit ok).

    A1 is handled upstream in the engine (always escalated with options), so it
    never reaches this function.
    """
    reasons: list[str] = []

    if len(plan.moves) > params.max_auto_displaced:
        reasons.append("too_many_displacements")

    if plan.cost > params.escalation_cost_threshold:
        reasons.append("cost_over_threshold")

    # No booked patient should be auto-pushed beyond the max auto-delay.
    if any(delay_minutes(m) > params.max_auto_delay_min for m in plan.moves):
        reasons.append("delay_over_auto_limit")

    # Note: the response-time window is enforced as a hard constraint in
    # ``candidate_rejections`` (A2-A5), so feasible plans already meet it.
    return tuple(reasons)
