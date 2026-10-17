"""The Cadence insertion engine: a bounded greedy cascade.

``insert_emergency`` takes an immutable state snapshot and an emergency request
and returns a :class:`Decision` with a chosen plan (or an escalation) plus the
alternatives considered and a full parameter snapshot. The algorithm:

1. Translate acuity into a response-time target.
2. For each eligible doctor, enumerate placement anchors (gaps + appointment
   boundaries) in a fixed order and build each candidate by rippling the
   displaced appointments later (bounded, gap-absorbing cascade).
3. Reject candidates that violate hard safety/fairness constraints.
4. Rank feasible candidates by the transparent cost function (deterministic
   tie-breaks) and either auto-recommend or escalate to a human.

Why greedy, not an optimiser: a greedy cascade produces a readable decision
trace and runs in milliseconds, which matters far more for an auditable clinical
tool than squeezing out a marginally cheaper global rearrangement.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Literal

from app.core.enums import Acuity
from app.scheduling.availability import Interval, fits_in_any
from app.scheduling.engine.constraints import candidate_rejections, escalation_reasons
from app.scheduling.engine.cost import delay_minutes, plan_cost
from app.scheduling.engine.types import (
    CandidatePlan,
    Decision,
    EngineAppointment,
    EngineParameters,
    EngineRequest,
    EngineState,
    Move,
    Placement,
)

_TOP_ALTERNATIVES = 4


def _align_up(dt: datetime, step_min: int) -> datetime:
    """Smallest grid-aligned instant >= ``dt`` (grid relative to the top of the hour)."""
    base = dt.replace(minute=0, second=0, microsecond=0)
    minutes = (dt - base).total_seconds() / 60.0
    steps = math.ceil(minutes / step_min - 1e-9)
    return base + timedelta(minutes=steps * step_min)


def _doctor_appointments(state: EngineState, doctor_id: int) -> list[EngineAppointment]:
    appts = [
        a for a in state.appointments if a.doctor_id == doctor_id and a.occupies_time
    ]
    return sorted(appts, key=lambda a: (a.start, a.id))


def _anchors(
    now: datetime,
    shifts: tuple[Interval, ...],
    appts: list[EngineAppointment],
    duration: timedelta,
    params: EngineParameters,
) -> list[datetime]:
    """Deterministic, bounded set of placement start-times to try."""
    raw: set[datetime] = {_align_up(now, params.slot_step_min)}
    for shift in shifts:
        raw.add(_align_up(max(now, shift.start), params.slot_step_min))
    for a in appts:
        raw.add(_align_up(max(now, a.start), params.slot_step_min))
        raw.add(_align_up(max(now, a.end), params.slot_step_min))
    # Keep only anchors whose emergency interval fits inside some shift.
    fitting = [s for s in raw if fits_in_any(Interval(s, s + duration), list(shifts))]
    return sorted(fitting)[: params.max_anchors_per_doctor]


def _build_candidate(
    doctor_id: int,
    start: datetime,
    duration: timedelta,
    appts: list[EngineAppointment],
    shifts: tuple[Interval, ...],
    request: EngineRequest,
    params: EngineParameters,
    *,
    enforce_window: bool,
    patient_busy: Mapping[int, tuple[Interval, ...]],
) -> CandidatePlan | None:
    """Build one candidate by inserting at ``start`` and rippling later appts.

    Returns None when the anchor is invalid (it would split an appointment that
    is already under way at ``start`` — we only insert at gaps or boundaries).
    """
    emergency = Interval(start, start + duration)

    # Reject anchors that fall in the middle of an existing appointment.
    if any(a.start < start < a.end for a in appts):
        return None

    affected = [a for a in appts if a.start >= start]
    moves: list[Move] = []
    displaced: dict[int, EngineAppointment] = {}
    cursor = emergency.end
    for a in sorted(affected, key=lambda x: (x.start, x.id)):
        if a.start >= cursor:
            break  # the gap absorbs the ripple; nothing further moves
        new_iv = Interval(cursor, cursor + a.duration)
        to_start: datetime | None = cursor if fits_in_any(new_iv, list(shifts)) else None
        moves.append(
            Move(
                a.id,
                a.doctor_id,
                a.start,
                to_start,
                "rippled_by_emergency",
                int(a.duration.total_seconds() // 60),
            )
        )
        displaced[a.id] = a
        if to_start is not None:
            cursor = new_iv.end

    survivors_busy = [a.interval for a in appts if a.id not in displaced]
    placement = Placement(doctor_id, emergency.start, emergency.end)
    rejections = candidate_rejections(
        placement,
        tuple(moves),
        request,
        displaced,
        survivors_busy,
        shifts,
        params,
        enforce_window=enforce_window,
        patient_busy=patient_busy,
    )
    cost = plan_cost(tuple(moves), displaced, params)
    return CandidatePlan(
        placement=placement,
        moves=tuple(moves),
        cost=cost,
        feasible=not rejections,
        reject_reasons=rejections,
    )


def _total_delay(plan: CandidatePlan) -> float:
    return sum(delay_minutes(m) for m in plan.moves)


def _rank_key(plan: CandidatePlan) -> tuple[float, datetime, float, int]:
    return (plan.cost, plan.placement.start, _total_delay(plan), plan.placement.doctor_id)


def insert_emergency(
    state: EngineState,
    request: EngineRequest,
    params: EngineParameters | None = None,
) -> Decision:
    params = params or EngineParameters()

    # A1 is human-directed, so timing is not a hard filter for it: we still want
    # to surface the soonest options rather than reject them all for being "late".
    enforce_window = request.acuity != Acuity.A1

    candidates: list[CandidatePlan] = []
    for doctor_id in request.eligible_doctor_ids:
        shifts = tuple(state.shifts.get(doctor_id, ()))
        if not shifts:
            continue
        appts = _doctor_appointments(state, doctor_id)
        duration = timedelta(minutes=request.duration_min)
        for anchor in _anchors(request.now, shifts, appts, duration, params):
            built = _build_candidate(
                doctor_id,
                anchor,
                duration,
                appts,
                shifts,
                request,
                params,
                enforce_window=enforce_window,
                patient_busy=state.patient_busy,
            )
            if built is not None:
                candidates.append(built)

    if not candidates:
        return Decision("infeasible", None, (), ("no_candidates",), request, params)

    feasible = [c for c in candidates if c.feasible]

    # A1 (critical) never auto-commits — a clinician decides, possibly choosing to
    # interrupt a consultation. We present ranked options (feasible if any, else
    # the least-bad candidates) without committing.
    if request.acuity == Acuity.A1:
        pool = feasible or candidates
        options = tuple(sorted(pool, key=_rank_key)[:_TOP_ALTERNATIVES])
        return Decision(
            "escalate", None, options, ("acuity_a1_human_directed",), request, params
        )

    # Routine (A5) arrivals never displace booked patients.
    if request.acuity == Acuity.A5:
        feasible = [c for c in feasible if not c.moves]

    if not feasible:
        worst = sorted(candidates, key=_rank_key)[:_TOP_ALTERNATIVES]
        return Decision(
            "escalate", None, tuple(worst), ("no_feasible_plan",), request, params
        )

    ranked = sorted(feasible, key=_rank_key)
    chosen = ranked[0]
    alternatives = tuple(ranked[1 : 1 + _TOP_ALTERNATIVES])

    reasons = escalation_reasons(chosen, request, params)
    status: Literal["auto", "escalate"] = "escalate" if reasons else "auto"
    return Decision(status, chosen, alternatives, reasons, request, params)
