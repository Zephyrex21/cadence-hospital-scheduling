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
    # Honoured ONLY when CADENCE_ALLOW_CLIENT_NOW is enabled (tests / pinned E2E).
    # In every real deployment the server clock is authoritative and this is ignored.
    now: datetime | None = None


class CommitRequest(PlanRequest):
    fingerprint: str = Field(min_length=1)
    idempotency_key: str | None = Field(default=None, max_length=80)
    # Digest of the plan the reviewer approved (from the plan response). If the
    # recomputed plan no longer matches, the commit is refused.
    plan_digest: str | None = Field(default=None, max_length=64)


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
    plan_digest: str | None = None
    # The server instant the plan was computed against (informational).
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


class OptionOut(PlanOut):
    index: int
    applicable: bool


class OptionsResponse(BaseModel):
    decision_id: int
    reasons: list[str]
    emergency_patient: PatientSummary
    options: list[OptionOut]
    appointment_details: dict[str, ApptDetail]
    doctor_names: dict[str, str]


class ApplyRequest(BaseModel):
    option_index: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=400)
