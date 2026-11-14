"""Scheduling request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import AppointmentOrigin, AppointmentStatus


class DoctorRead(BaseModel):
    id: int
    name: str
    specialty: str


class AppointmentTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    default_duration_min: int
    specialty: str


class ShiftRead(BaseModel):
    id: int
    doctor_id: int
    start: datetime
    end: datetime


class PatientSummary(BaseModel):
    id: int
    name: str
    mrn: str


class AppointmentRead(BaseModel):
    id: int
    status: AppointmentStatus
    origin: AppointmentOrigin
    scheduled_start: datetime
    scheduled_end: datetime
    version: int
    patient: PatientSummary
    doctor: DoctorRead
    type: AppointmentTypeRead


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    type_id: int
    scheduled_start: datetime

    @field_validator("scheduled_start")
    @classmethod
    def _needs_timezone(cls, value: datetime) -> datetime:
        # "10:00" without a zone is ambiguous (UTC? clinic time?) — refuse to guess.
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "scheduled_start must include a timezone, e.g. 2026-11-16T10:00:00+05:30 or ...Z"
            )
        return value


class SlotRead(BaseModel):
    start: datetime
    end: datetime


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
    version: int | None = Field(
        default=None, description="If provided, must match current version (optimistic lock)."
    )
