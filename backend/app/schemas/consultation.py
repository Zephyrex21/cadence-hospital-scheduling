"""Queue and consultation-status schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

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
