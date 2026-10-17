"""Triage request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Acuity


class TriageCreate(BaseModel):
    patient_id: int
    acuity: Acuity
    chief_complaint: str = Field(min_length=1, max_length=255)
    vitals: dict[str, Any] | None = None


class TriageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    nurse_id: int
    acuity: Acuity
    chief_complaint: str
    vitals: dict[str, Any] | None
    assessed_at: datetime
