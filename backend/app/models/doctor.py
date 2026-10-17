"""Doctor profile: clinical attributes layered onto a staff user with role=doctor.

A doctor is a ``User`` (role=doctor); this one-to-one table adds the schedulable
attributes (specialty) without duplicating identity/auth data.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    specialty: Mapped[str] = mapped_column(String(60), nullable=False, default="general")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<DoctorProfile user_id={self.user_id} specialty={self.specialty!r}>"
