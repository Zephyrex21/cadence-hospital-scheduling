"""Queue and consultation-status schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import Acuity, AppointmentStatus, ConsultationAction


class QueuePatient(BaseModel):
    id: int
    name: str
    mrn: str


class QueueDoctor(BaseModel):
    id: int
    name: str


class QueueEntryOut(BaseModel):
    appointment_id: int
    position: int
    est_wait_min: int
    waiting: bool
    acuity: Acuity
    status: AppointmentStatus
    scheduled_start: datetime
    patient: QueuePatient
    doctor: QueueDoctor
    type_name: str


class StatusChangeRequest(BaseModel):
    action: ConsultationAction
    version: int | None = None


class StatusChangeResponse(BaseModel):
    id: int
    status: AppointmentStatus
    version: int


class ExtendRequest(BaseModel):
    minutes: int = Field(ge=5, le=120)
    version: int | None = None


class ExtendDisplaced(BaseModel):
    appointment_id: int
    patient_name: str
    from_start: datetime
    to_start: datetime


class ExtendResponse(BaseModel):
    id: int
    scheduled_end: datetime
    version: int
    decision_id: int | None
    displaced: list[ExtendDisplaced]
