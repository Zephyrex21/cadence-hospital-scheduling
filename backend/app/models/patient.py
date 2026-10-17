"""Patient model. All patient data in Cadence is synthetic (development only)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Human-friendly synthetic medical record number, e.g. "CAD-004271".
    mrn: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(16), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(120), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Patient id={self.id} mrn={self.mrn!r}>"
