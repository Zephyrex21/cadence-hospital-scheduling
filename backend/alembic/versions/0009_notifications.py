"""Patient notification outbox.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=True),
        sa.Column(
            "decision_id", sa.Integer(), sa.ForeignKey("scheduling_decisions.id"), nullable=True
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("channel", sa.String(12), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("recipient", sa.String(32), nullable=True),
        sa.Column("body", sa.String(600), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("error", sa.String(255), nullable=True),
        sa.Column("provider_ref", sa.String(80), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_patient_id", "notifications", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_patient_id", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_table("notifications")
