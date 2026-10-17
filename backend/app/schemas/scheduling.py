"""Scheduling request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

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


class SlotRead(BaseModel):
    start: datetime
    end: datetime


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)
    version: int | None = Field(
        default=None, description="If provided, must match current version (optimistic lock)."
    )
