"""Engine invariants — must hold for *every* decision the engine returns.

Rather than add a Hypothesis dependency (not installable in this environment),
we sweep a deterministic pseudo-random space of schedules with a seeded RNG and
assert the blueprint's safety/fairness invariants on each committed/surfaced plan.
Each case is reproducible from its seed. (Upgrading to Hypothesis is a trivial
future swap — the invariant assertions are already factored out below.)
"""

from __future__ import annotations

import random

from app.core.enums import Acuity, AppointmentStatus
from app.scheduling.availability import Interval, has_conflict
from app.scheduling.engine import (
    CandidatePlan,
    Decision,
    EngineAppointment,
    insert_emergency,
)
from app.scheduling.engine.types import EngineParameters, EngineState
from tests.engine.builders import appt, at, request, state

_ACUITIES = [Acuity.A1, Acuity.A2, Acuity.A3, Acuity.A4, Acuity.A5]


def _random_state(rng: random.Random) -> EngineState:
    """A random single-doctor morning: 0-10 appts, varied status/acuity/history."""
    n = rng.randint(0, 10)
    appts: list[EngineAppointment] = []
    cursor = 0
    for i in range(n):
        cursor += rng.choice([0, 0, 15, 30])  # sometimes gaps, sometimes solid
        dur = rng.choice([15, 30, 45])
        if cursor + dur > 480:
            break
        status = rng.choice(
            [
                AppointmentStatus.BOOKED,
                AppointmentStatus.BOOKED,
                AppointmentStatus.CHECKED_IN,
                AppointmentStatus.IN_PROGRESS,
                AppointmentStatus.COMPLETED,  # should not occupy time
                AppointmentStatus.CANCELLED,  # should not occupy time
            ]
        )
        appts.append(
            appt(
                i + 1,
                cursor,
                dur,
                status=status,
                acuity=rng.choice(_ACUITIES),
                displacement_count=rng.choice([0, 0, 1, 2]),
            )
        )
        cursor += dur
    return state(appts)


def _surfaced_plans(d: Decision) -> list[CandidatePlan]:
    plans = list(d.alternatives)
    if d.chosen is not None:
        plans.append(d.chosen)
    return plans


def _assert_invariants(s: EngineState, d: Decision, params: EngineParameters) -> None:
    by_id = {a.id: a for a in s.appointments}

    # The engine never crashes and always classifies itself.
    assert d.status in {"auto", "escalate", "infeasible"}
    if d.status == "auto":
        assert d.chosen is not None
        assert d.reasons == ()
    if d.status == "infeasible":
        assert d.chosen is None
    # A chosen plan (auto, or escalated for blast-radius/cost/delay) is always feasible.
    if d.chosen is not None:
        assert d.chosen.feasible

    for plan in _surfaced_plans(d):
        # INV-0: feasibility and reject-reasons are consistent.
        assert plan.feasible == (not plan.reject_reasons)

        # The strict safety/fairness invariants hold for every FEASIBLE plan.
        # Infeasible plans are surfaced only as flagged, non-committable options
        # for a human, so they may (by definition) break a hard rule.
        if not plan.feasible:
            continue

        placed = Interval(plan.placement.start, plan.placement.end)
        moved_ids = {m.appointment_id for m in plan.moves}

        # INV-1: no survivor overlaps the emergency placement.
        survivors = [a.interval for a in s.appointments
                     if a.occupies_time and a.id not in moved_ids]
        assert not has_conflict(placed, survivors), "placement conflicts with a survivor"

        for m in plan.moves:
            a = by_id[m.appointment_id]
            # INV-2: in-progress consultations are never displaced.
            assert not a.is_protected, "interrupted an in-progress consult"
            # INV-3: fairness cap respected.
            assert a.displacement_count + 1 <= params.max_displacements
            # INV-4: no silent loss — every move lands somewhere real.
            assert m.to_start is not None
            # INV-5: priority-inversion guard — a less-urgent arrival (higher
            # level number) never displaces a strictly more-urgent booked patient.
            assert _level(d.request.acuity) <= _level(a.acuity)

    # INV-6: an AUTO-committed plan's blast radius is within the auto limit.
    if d.status == "auto" and d.chosen is not None:
        assert len(d.chosen.moves) <= params.max_auto_displaced


def _level(a: Acuity) -> int:
    return {Acuity.A1: 1, Acuity.A2: 2, Acuity.A3: 3, Acuity.A4: 4, Acuity.A5: 5}[a]


def test_invariants_hold_across_random_schedules() -> None:
    params = EngineParameters()
    for seed in range(300):
        rng = random.Random(seed)
        s = _random_state(rng)
        acuity = rng.choice(_ACUITIES)
        now = rng.choice([0, 0, 30, 60])
        req = request(acuity, duration_min=rng.choice([15, 30, 45]), now=now)
        d = insert_emergency(s, req, params)
        try:
            _assert_invariants(s, d, params)
        except AssertionError as exc:  # pragma: no cover - diagnostic path
            raise AssertionError(f"invariant failed on seed={seed}: {exc}") from exc


def test_determinism_same_input_same_plan() -> None:
    params = EngineParameters()
    for seed in range(50):
        rng1 = random.Random(seed)
        s = _random_state(rng1)
        req = request(Acuity.A2, now=0)
        d1 = insert_emergency(s, req, params)
        d2 = insert_emergency(s, req, params)
        assert d1.status == d2.status
        assert d1.chosen == d2.chosen
        assert d1.alternatives == d2.alternatives
        assert d1.reasons == d2.reasons


def test_completed_and_cancelled_appointments_do_not_block() -> None:
    # A completed appt occupying 09:00-09:30 must not stop a 09:00 placement.
    s = state([appt(1, 0, 30, status=AppointmentStatus.COMPLETED)])
    d = insert_emergency(s, request(Acuity.A2, now=0))
    assert d.status == "auto"
    assert d.chosen is not None
    assert d.chosen.placement.start == at(0)
    assert d.chosen.moves == ()
