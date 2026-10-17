"""scheduling: doctor_profiles, appointment_types, shifts, appointments

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "doctor_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("specialty", sa.String(length=60), nullable=False, server_default="general"),
    )

    op.create_table(
        "appointment_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("default_duration_min", sa.Integer(), nullable=False),
        sa.Column("specialty", sa.String(length=60), nullable=False, server_default="general"),
    )
    op.create_index("ix_appointment_types_name", "appointment_types", ["name"], unique=True)

    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_utc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_shifts_doctor_id", "shifts", ["doctor_id"])
    op.create_index("ix_shifts_doctor_start", "shifts", ["doctor_id", "start_utc"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type_id", sa.Integer(), sa.ForeignKey("appointment_types.id"), nullable=False),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="booked"),
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="booked"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index("ix_appointments_doctor_id", "appointments", ["doctor_id"])
    op.create_index(
        "ix_appointments_doctor_start", "appointments", ["doctor_id", "scheduled_start"]
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_doctor_start", table_name="appointments")
    op.drop_index("ix_appointments_doctor_id", table_name="appointments")
    op.drop_index("ix_appointments_patient_id", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_shifts_doctor_start", table_name="shifts")
    op.drop_index("ix_shifts_doctor_id", table_name="shifts")
    op.drop_table("shifts")
    op.drop_index("ix_appointment_types_name", table_name="appointment_types")
    op.drop_table("appointment_types")
    op.drop_table("doctor_profiles")
