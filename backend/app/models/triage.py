"""Triage assessment — a licensed nurse's recorded clinical judgment.

Acuity is set here, by a human, and never by the scheduling engine. The engine
only consumes the acuity to arrange time; it never diagnoses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import Acuity
from app.models.base import utcnow

_acuity_type = Enum(
    Acuity,
    native_enum=False,
    length=4,
    values_callable=lambda enum: [member.value for member in enum],
)


class TriageAssessment(Base):
    __tablename__ = "triage_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    nurse_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    acuity: Mapped[Acuity] = mapped_column(_acuity_type, nullable=False)
    chief_complaint: Mapped[str] = mapped_column(String(255), nullable=False)
    vitals: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    # Set when this assessment has been used to schedule an emergency. One
    # assessment authorises exactly one insertion; a new walk-in episode needs a
    # fresh nurse assessment.
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
