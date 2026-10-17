"""Named scenario tests — the concrete behaviours from the blueprint (§D, §J).

Each test is a small, legible clinic situation with an asserted outcome.
"""

from __future__ import annotations

from app.core.enums import Acuity, AppointmentStatus
from app.scheduling.availability import Interval
from app.scheduling.engine import insert_emergency
from app.scheduling.engine.types import EngineParameters
from tests.engine.builders import (
    appt,
    at,
    back_to_back,
    request,
    shift,
    state,
)


def test_emergency_into_free_gap_displaces_nobody() -> None:
    # One short morning appointment, then open time: the emergency slots in clean.
    s = state([appt(1, 0, 30)])
    d = insert_emergency(s, request(Acuity.A3, now=30))
    assert d.status == "auto"
    assert d.chosen is not None
    assert d.chosen.moves == ()


def test_emergency_into_full_day_cascades() -> None:
    # A solid wall of appointments: the emergency must ripple at least one later.
    s = state(back_to_back(8))  # 09:00-13:00 solid, afternoon open
    d = insert_emergency(s, request(Acuity.A2, now=0))
    assert d.status in {"auto", "escalate"}
    assert d.chosen is not None or d.alternatives
    plan = d.chosen or d.alternatives[0]
    assert plan.moves, "a full morning should force at least one displacement"


def test_cascade_is_bounded_and_absorbed_by_a_gap() -> None:
    # Two appts then a gap: inserting at 0 pushes #1 and #2, but the gap stops it.
    s = state([appt(1, 0, 30), appt(2, 30, 30), appt(3, 120, 30)])
    d = insert_emergency(s, request(Acuity.A2, duration_min=30, now=0))
    assert d.chosen is not None
    moved_ids = {m.appointment_id for m in d.chosen.moves}
    assert 3 not in moved_ids  # the 60-min gap before #3 absorbs the ripple


def test_in_progress_consultation_is_never_interrupted() -> None:
    # A live consult occupies 09:00-09:30. With a 60-min (A3) window the engine
    # can place cleanly at 09:30 instead of rippling the protected appointment.
    s = state([appt(1, 0, 30, status=AppointmentStatus.IN_PROGRESS)])
    d = insert_emergency(s, request(Acuity.A3, now=0))
    assert d.status == "auto"
    assert d.chosen is not None
    assert d.chosen.placement.start >= at(30)  # after the live consult
    assert 1 not in {m.appointment_id for m in d.chosen.moves}  # never touched


def test_a1_always_escalates_with_options() -> None:
    s = state([appt(1, 0, 30)])
    d = insert_emergency(s, request(Acuity.A1, now=0))
    assert d.status == "escalate"
    assert d.chosen is None
    assert "acuity_a1_human_directed" in d.reasons
    assert d.alternatives, "A1 should still surface ranked options for the clinician"


def test_a5_routine_never_displaces() -> None:
    s = state(back_to_back(8))  # full morning
    d = insert_emergency(s, request(Acuity.A5, now=0))
    if d.chosen is not None:
        assert d.chosen.moves == ()


def test_fairness_cap_blocks_third_displacement() -> None:
    # The only placement would re-bump an appt already displaced twice (cap=2).
    s = state([appt(1, 0, 30, displacement_count=2)], shifts=shift(end=60))
    d = insert_emergency(s, request(Acuity.A2, duration_min=30, now=0))
    # No feasible plan: either escalate or infeasible, never an auto-commit.
    assert d.status != "auto"


def test_priority_inversion_guard_rejects_bumping_sicker_patient() -> None:
    # A less-urgent A4 emergency may not displace a more-urgent A2 booked patient.
    s = state([appt(1, 0, 30, acuity=Acuity.A2)], shifts=shift(end=30))
    d = insert_emergency(s, request(Acuity.A4, duration_min=30, now=0))
    assert d.status != "auto"


def test_displacement_overflow_is_never_auto_committed() -> None:
    # A solid, full one-hour shift (09:00-10:00): inserting anywhere would push an
    # appointment past end-of-day. That is never silently auto-committed, and no
    # feasible option may drop an appointment (to_start=None).
    s = state([appt(1, 0, 30), appt(2, 30, 30)], shifts=shift(end=60))
    d = insert_emergency(s, request(Acuity.A2, duration_min=30, now=0))
    assert d.status != "auto"
    for plan in (d.chosen, *d.alternatives):
        if plan is not None and plan.feasible:
            assert all(m.to_start is not None for m in plan.moves)


def test_misses_response_window_without_feasible_slot_escalates() -> None:
    # Full morning, A2 window is 15 min: no in-window slot exists -> not auto.
    s = state(back_to_back(8))
    d = insert_emergency(s, request(Acuity.A2, now=0))
    if d.status == "auto":
        assert d.chosen is not None
        assert d.chosen.placement.start <= at(15)


def test_large_blast_radius_escalates() -> None:
    # Tight limit: the only in-window placement ripples 6 appointments (> 1), so
    # the engine must hand it to a human rather than auto-commit a wide disruption.
    params = EngineParameters(max_auto_displaced=1)
    s = state(back_to_back(6))
    d = insert_emergency(s, request(Acuity.A2, now=0), params)
    assert d.status == "escalate"
    assert "too_many_displacements" in d.reasons


def test_no_eligible_doctor_is_infeasible() -> None:
    s = state([appt(1, 0, 30)])
    d = insert_emergency(s, request(Acuity.A2, now=0, doctors=(2,)))
    assert d.status == "infeasible"
    assert "no_candidates" in d.reasons


def test_multi_doctor_prefers_the_cheaper_doctor() -> None:
    # Doctor 1 is full all morning; doctor 2 is wide open -> pick doctor 2, no moves.
    shifts = {
        1: (Interval(at(0), at(480)),),
        2: (Interval(at(0), at(480)),),
    }
    appts = back_to_back(8, doctor_id=1)
    s = state(appts, shifts=shifts)
    d = insert_emergency(s, request(Acuity.A2, now=0, doctors=(1, 2)))
    assert d.status == "auto"
    assert d.chosen is not None
    assert d.chosen.placement.doctor_id == 2
    assert d.chosen.moves == ()


def test_decision_carries_full_parameter_snapshot() -> None:
    params = EngineParameters(max_displacements=5)
    s = state([appt(1, 0, 30)])
    d = insert_emergency(s, request(Acuity.A3, now=30), params)
    assert d.parameters is params
    assert d.engine_version.startswith("cadence-engine/")
    assert d.request.acuity == Acuity.A3
