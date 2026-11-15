"""Notification schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NotificationPatient(BaseModel):
    id: int
    name: str
    mrn: str


class NotificationOut(BaseModel):
    id: int
    created_at: datetime
    sent_at: datetime | None
    kind: str
    channel: str
    provider: str
    recipient: str | None  # masked: the full number never leaves the server
    body: str
    status: str
    error: str | None
    attempts: int
    appointment_id: int | None
    decision_id: int | None
    patient: NotificationPatient
