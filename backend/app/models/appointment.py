"""Appointment model.

Status/origin are stored as portable VARCHAR+CHECK enums (identical on PostgreSQL
and the SQLite used in tests). ``version`` backs optimistic locking on mutation.
All datetimes are UTC.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import Acuity, AppointmentOrigin, AppointmentStatus
from app.models.base import TimestampMixin, UtcDateTime

if TYPE_CHECKING:
    from app.models.appointment_type import AppointmentType
    from app.models.patient import Patient
    from app.models.user import User

_status_type = Enum(
    AppointmentStatus,
    native_enum=False,
    length=20,
    values_callable=lambda enum: [member.value for member in enum],
)
_origin_type = Enum(
    AppointmentOrigin,
    native_enum=False,
    length=20,
    values_callable=lambda enum: [member.value for member in enum],
)
_acuity_type = Enum(
    Acuity,
    native_enum=False,
    length=4,
    values_callable=lambda enum: [member.value for member in enum],
)


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("appointment_types.id"), nullable=False)
    scheduled_start: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        _status_type, nullable=False, default=AppointmentStatus.BOOKED
    )
    origin: Mapped[AppointmentOrigin] = mapped_column(
        _origin_type, nullable=False, default=AppointmentOrigin.BOOKED
    )
    # Clinical acuity (A5/routine for ordinary bookings; set from triage for
    # emergencies). ``displacement_count`` backs the engine's fairness cap.
    acuity: Mapped[Acuity] = mapped_column(_acuity_type, nullable=False, default=Acuity.A5)
    displacement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Eager-loaded: the schedule view always serializes these together, and the
    # sets are small (one clinic-day), so a join avoids N+1 without cost.
    patient: Mapped["Patient"] = relationship(lazy="joined")
    doctor: Mapped["User"] = relationship(foreign_keys=[doctor_id], lazy="joined")
    type: Mapped["AppointmentType"] = relationship(lazy="joined")

    __table_args__ = (Index("ix_appointments_doctor_start", "doctor_id", "scheduled_start"),)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Appointment id={self.id} doctor={self.doctor_id} start={self.scheduled_start}>"
