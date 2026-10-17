"""Emergency plan/commit request and response schemas.

The response models mirror the engine adapter's serialized ``Decision`` so the
frontend gets a typed contract (via OpenAPI) for the plan-diff review screen.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import Acuity


class PlanRequest(BaseModel):
    patient_id: int
    type_id: int
    acuity: Acuity
    # Optional explicit "now" (for the synthetic demo / tests); defaults to UTC now.
    now: datetime | None = None


class CommitRequest(PlanRequest):
    fingerprint: str = Field(min_length=1)
    idempotency_key: str | None = Field(default=None, max_length=80)


# --- serialized Decision shapes ---------------------------------------------


class MoveOut(BaseModel):
    appointment_id: int
    doctor_id: int
    from_start: datetime
    to_start: datetime | None
    delay_min: float | None
    duration_min: int
    reason: str


class PlacementOut(BaseModel):
    doctor_id: int
    start: datetime
    end: datetime


class PlanOut(BaseModel):
    placement: PlacementOut
    cost: float
    feasible: bool
    reject_reasons: list[str]
    moves: list[MoveOut]


class RequestOut(BaseModel):
    patient_id: int
    acuity: Acuity
    duration_min: int
    now: datetime
    eligible_doctor_ids: list[int]


class DecisionOut(BaseModel):
    status: str
    engine_version: str
    reasons: list[str]
    request: RequestOut
    parameters: dict[str, Any]
    chosen: PlanOut | None
    alternatives: list[PlanOut]


class PatientSummary(BaseModel):
    id: int
    name: str
    mrn: str


class ApptDetail(BaseModel):
    patient_name: str
    mrn: str
    type_name: str
    doctor_name: str
    acuity: Acuity


class PlanResponse(BaseModel):
    fingerprint: str
    # The instant the plan was computed against — echoed back on commit so the
    # server can reject a plan that has since gone stale (see PLAN_MAX_AGE).
    now: datetime
    decision: DecisionOut
    emergency_patient: PatientSummary
    appointment_details: dict[str, ApptDetail]
    doctor_names: dict[str, str]


class DisplacedOut(BaseModel):
    appointment_id: int
    patient_name: str
    from_start: datetime
    to_start: datetime


class CommitResponse(BaseModel):
    status: str  # "auto" | "escalate"
    decision_id: int
    emergency_appointment_id: int | None
    reasons: list[str]
    displaced: list[DisplacedOut]
