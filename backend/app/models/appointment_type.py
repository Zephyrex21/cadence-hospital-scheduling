"""Appointment type with the default duration the scheduler uses to size a slot."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AppointmentType(Base):
    __tablename__ = "appointment_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    default_duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    specialty: Mapped[str] = mapped_column(String(60), nullable=False, default="general")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<AppointmentType id={self.id} name={self.name!r}>"
