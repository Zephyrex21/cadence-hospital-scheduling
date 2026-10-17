"""Doctor availability window.

MVP uses concrete rows (one per working block) rather than a recurrence-rule
engine — deliberately simple and easy to reason about. All times are UTC.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import UtcDateTime


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    start_utc: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    end_utc: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)

    __table_args__ = (Index("ix_shifts_doctor_start", "doctor_id", "start_utc"),)
