"""Staff user model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import Role
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.doctor import DoctorProfile

# ``native_enum=False`` stores the role as a portable VARCHAR + CHECK constraint,
# identical on PostgreSQL and SQLite. ``values_callable`` persists the lowercase
# values ("doctor") rather than the enum member names.
_role_type = Enum(
    Role,
    native_enum=False,
    length=20,
    values_callable=lambda enum: [member.value for member in enum],
)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(_role_type, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Present only for role=doctor; None otherwise. Eager-loaded for schedule reads.
    doctor_profile: Mapped["DoctorProfile | None"] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
