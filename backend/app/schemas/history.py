"""Read-side history schemas: displacements, decision traces, audit log."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DisplacementOut(BaseModel):
    id: int
    appointment_id: int
    decision_id: int
    patient_name: str
    mrn: str
    doctor_name: str
    from_start: datetime
    to_start: datetime
    delay_min: int
    reason: str
    created_at: datetime


class DecisionSummaryOut(BaseModel):
    id: int
    created_at: datetime
    trigger: str
    status: str
    engine_version: str
    patient_name: str
    actor_name: str
    emergency_appointment_id: int | None
    reason_count: int
    displaced_count: int


class DecisionActor(BaseModel):
    id: int
    name: str


class DecisionPatient(BaseModel):
    id: int
    name: str
    mrn: str


class DecisionDisplaced(BaseModel):
    appointment_id: int
    patient_name: str
    from_start: datetime
    to_start: datetime
    delay_min: int
    reason: str


class DecisionDetailOut(BaseModel):
    id: int
    trigger: str
    status: str
    engine_version: str
    created_at: datetime
    actor: DecisionActor
    patient: DecisionPatient
    emergency_appointment_id: int | None
    reasons: list[str]
    chosen_plan: dict[str, Any] | None
    alternatives: list[Any]
    parameters: dict[str, Any]
    input_snapshot: dict[str, Any]
    displacements: list[DecisionDisplaced]


class AuditEntryOut(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    action: str
    actor_name: str
    reason: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime


class ResolveRequest(BaseModel):
    note: str = Field(min_length=1, max_length=500)


class ResolvedBy(BaseModel):
    id: int
    name: str


class ResolveResponse(BaseModel):
    id: int
    resolved_at: datetime
    resolved_by: ResolvedBy
    resolution_note: str
