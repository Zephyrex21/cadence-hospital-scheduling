"""Cadence scheduling engine — pure, deterministic, dependency-free.

Public API:

    from app.scheduling.engine import insert_emergency, EngineState, EngineRequest

The engine never touches the database. The service layer (Phase 4) maps ORM rows
into an ``EngineState``, calls ``insert_emergency``, and applies the resulting
plan transactionally.
"""

from __future__ import annotations

from app.scheduling.engine.engine import insert_emergency, plan_at
from app.scheduling.engine.types import (
    ACUITY_LEVEL,
    ENGINE_VERSION,
    CandidatePlan,
    Decision,
    DecisionStatus,
    EngineAppointment,
    EngineParameters,
    EngineRequest,
    EngineState,
    Move,
    Placement,
    default_response_windows,
)

__all__ = [
    "insert_emergency",
    "plan_at",
    "EngineState",
    "EngineRequest",
    "EngineParameters",
    "EngineAppointment",
    "Decision",
    "DecisionStatus",
    "CandidatePlan",
    "Move",
    "Placement",
    "ACUITY_LEVEL",
    "ENGINE_VERSION",
    "default_response_windows",
]
