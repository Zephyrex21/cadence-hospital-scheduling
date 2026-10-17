"""Appointment displacement — one row per appointment moved by an emergency.

Powers the "displaced / rescheduled" screen and gives the fairness policy a
durable record of how often each appointment has been bumped.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import utcnow


class AppointmentDisplacement(Base):
    __tablename__ = "appointment_displacements"

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"), nullable=False, index=True
    )
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("scheduling_decisions.id"), nullable=False, index=True
    )
    from_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
