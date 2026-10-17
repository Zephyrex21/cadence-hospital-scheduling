"""emergency: appointment acuity/displacement, triage, decisions, displacements

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("acuity", sa.String(length=4), nullable=False, server_default="a5"),
    )
    op.add_column(
        "appointments",
        sa.Column("displacement_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "triage_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("nurse_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("acuity", sa.String(length=4), nullable=False),
        sa.Column("chief_complaint", sa.String(length=255), nullable=False),
        sa.Column("vitals", sa.JSON(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_triage_patient_id", "triage_assessments", ["patient_id"])
    op.create_index("ix_triage_assessed_at", "triage_assessments", ["assessed_at"])

    op.create_table(
        "scheduling_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trigger", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("engine_version", sa.String(length=60), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column(
            "emergency_appointment_id",
            sa.Integer(),
            sa.ForeignKey("appointments.id"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(length=80), nullable=True),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("chosen_plan", sa.JSON(), nullable=True),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_decisions_idempotency_key",
        "scheduling_decisions",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index("ix_decisions_created_at", "scheduling_decisions", ["created_at"])

    op.create_table(
        "appointment_displacements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False
        ),
        sa.Column(
            "decision_id",
            sa.Integer(),
            sa.ForeignKey("scheduling_decisions.id"),
            nullable=False,
        ),
        sa.Column("from_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_displacements_appointment_id", "appointment_displacements", ["appointment_id"]
    )
    op.create_index("ix_displacements_decision_id", "appointment_displacements", ["decision_id"])
    op.create_index("ix_displacements_created_at", "appointment_displacements", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_displacements_created_at", table_name="appointment_displacements")
    op.drop_index("ix_displacements_decision_id", table_name="appointment_displacements")
    op.drop_index("ix_displacements_appointment_id", table_name="appointment_displacements")
    op.drop_table("appointment_displacements")
    op.drop_index("ix_decisions_created_at", table_name="scheduling_decisions")
    op.drop_index("ix_decisions_idempotency_key", table_name="scheduling_decisions")
    op.drop_table("scheduling_decisions")
    op.drop_index("ix_triage_assessed_at", table_name="triage_assessments")
    op.drop_index("ix_triage_patient_id", table_name="triage_assessments")
    op.drop_table("triage_assessments")
    op.drop_column("appointments", "displacement_count")
    op.drop_column("appointments", "acuity")
