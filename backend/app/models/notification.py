"""Patient notification outbox.

One row per message to a patient (e.g. "your appointment was moved"). Rows are written in the
same transaction as the schedule change that caused them, so a notification can never exist for
a change that rolled back, nor be lost for one that committed. Delivery happens afterwards.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import utcnow


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_status", "status"),
        Index("ix_notifications_created_at", "created_at"),
        Index("ix_notifications_patient_id", "patient_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    decision_id: Mapped[int | None] = mapped_column(
        ForeignKey("scheduling_decisions.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # appointment_moved
    channel: Mapped[str] = mapped_column(String(12), nullable=False)  # sms|whatsapp|none
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # console|twilio
    recipient: Mapped[str | None] = mapped_column(String(32), nullable=True)
    body: Mapped[str] = mapped_column(String(600), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)  # queued|sent|failed|skipped
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
