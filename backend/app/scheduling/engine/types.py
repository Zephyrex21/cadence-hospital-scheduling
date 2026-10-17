"""Pure data types for the Cadence scheduling engine (no database, no I/O).

The engine takes an immutable ``EngineState`` snapshot plus an ``EngineRequest``
(the emergency to insert) and returns a ``Decision`` carrying the chosen plan,
the alternatives considered, their costs, and the parameter snapshot. Purity is
deliberate: it makes every scheduling invariant unit-testable without a database
and makes decisions reproducible — the same (state, request, parameters,
engine_version) always yields the same plan.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from app.core.enums import Acuity, AppointmentStatus
from app.scheduling.availability import Interval

ENGINE_VERSION = "cadence-engine/0.1-greedy-cascade"

# Lower level == more urgent. Used by the priority-inversion guard and cost.
ACUITY_LEVEL: Mapping[Acuity, int] = {
    Acuity.A1: 1,
    Acuity.A2: 2,
    Acuity.A3: 3,
    Acuity.A4: 4,
    Acuity.A5: 5,
}

# Minutes from ``now`` within which an arrival of each acuity should be seen.
# A5 is effectively "never displaces" (handled explicitly in the engine).
_WINDOW_SENTINEL = 10_000


def default_response_windows() -> dict[Acuity, int]:
    return {
        Acuity.A1: 0,
        Acuity.A2: 15,
        Acuity.A3: 60,
        Acuity.A4: 120,
        Acuity.A5: _WINDOW_SENTINEL,
    }


@dataclass(frozen=True)
class EngineAppointment:
    """A booked appointment as the engine sees it (mapped from an ORM row)."""

    id: int
    doctor_id: int
    patient_id: int
    start: datetime
    end: datetime
    status: AppointmentStatus
    acuity: Acuity = Acuity.A5
    displacement_count: int = 0

    @property
    def interval(self) -> Interval:
        return Interval(self.start, self.end)

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    @property
    def is_protected(self) -> bool:
        """In-progress consultations are never displaced by the engine."""
        return self.status == AppointmentStatus.IN_PROGRESS

    @property
    def occupies_time(self) -> bool:
        """Only live appointments consume schedule time."""
        return self.status in {
            AppointmentStatus.BOOKED,
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.IN_PROGRESS,
        }


@dataclass(frozen=True)
class EngineRequest:
    """The emergency arrival to insert into the schedule."""

    patient_id: int
    acuity: Acuity
    duration_min: int
    eligible_doctor_ids: tuple[int, ...]
    now: datetime


@dataclass(frozen=True)
class EngineState:
    """Immutable snapshot of the world the engine reasons over."""

    shifts: Mapping[int, tuple[Interval, ...]]
    appointments: tuple[EngineAppointment, ...]
    # Each patient's own active appointments on doctors *outside* this run's
    # eligible set, so the engine never places (or ripples) an appointment into a
    # time the patient is already booked elsewhere. Keyed by patient id; absent
    # patients have no such commitments. Defaulted so existing call sites that
    # only pass shifts + appointments keep working.
    patient_busy: Mapping[int, tuple[Interval, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineParameters:
    """Tunable policy, snapshotted into every decision for reproducibility."""

    response_window_min: Mapping[Acuity, int] = field(default_factory=default_response_windows)
    max_displacements: int = 2          # hard fairness cap (rolling window)
    max_auto_delay_min: int = 30        # a booked patient pushed beyond this -> escalate
    max_auto_displaced: int = 3         # plans touching more than this -> escalate
    slot_step_min: int = 15             # grid alignment for candidate anchors
    max_anchors_per_doctor: int = 48    # bound candidate enumeration
    escalation_cost_threshold: float = 1000.0
    # cost weights
    w_delay: float = 1.0
    w_count: float = 15.0
    w_continuity: float = 50.0
    w_fairness_base: float = 1.0        # k in (1 + k) ** displacement_count


@dataclass(frozen=True)
class Move:
    """One displaced appointment. ``to_start`` is None when it cannot be placed
    (overflow past availability) — which makes the owning candidate infeasible.
    ``duration_min`` is the displaced appointment's own length (not the
    emergency's), so a before/after view can size each block correctly."""

    appointment_id: int
    doctor_id: int
    from_start: datetime
    to_start: datetime | None
    reason: str
    duration_min: int = 0


@dataclass(frozen=True)
class Placement:
    doctor_id: int
    start: datetime
    end: datetime


@dataclass(frozen=True)
class CandidatePlan:
    placement: Placement
    moves: tuple[Move, ...]
    cost: float
    feasible: bool
    reject_reasons: tuple[str, ...]


DecisionStatus = Literal["auto", "escalate", "infeasible"]


@dataclass(frozen=True)
class Decision:
    """The engine's answer and its full, replayable trace."""

    status: DecisionStatus
    chosen: CandidatePlan | None
    alternatives: tuple[CandidatePlan, ...]
    reasons: tuple[str, ...]
    request: EngineRequest
    parameters: EngineParameters
    engine_version: str = ENGINE_VERSION
