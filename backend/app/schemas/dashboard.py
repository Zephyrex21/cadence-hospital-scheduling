"""Dashboard summary schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DoctorLoad(BaseModel):
    doctor_id: int
    name: str
    waiting: int
    in_progress: int
    running_delay_min: int


class EscalationItem(BaseModel):
    decision_id: int
    patient_name: str
    created_at: datetime
    reasons: list[str]


class DashboardSummary(BaseModel):
    now: datetime
    total_waiting: int
    in_progress: int
    completed_today: int
    displaced_today: int
    escalations_pending: int
    # Keyed by acuity value ("a1".."a5"); kept as plain strings to avoid any
    # enum-key coercion surprises on serialization.
    waiting_by_acuity: dict[str, int]
    recent_escalations: list[EscalationItem]
    doctor_load: list[DoctorLoad]
