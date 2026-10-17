"""escalation resolution: resolved_at / resolved_by / resolution_note

Adds the escalation lifecycle columns to ``scheduling_decisions`` so an
escalated decision can be marked resolved (by a nurse or administrator, with a
note). The dashboard counts and lists only unresolved escalations.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-15
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scheduling_decisions",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scheduling_decisions",
        sa.Column("resolved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "scheduling_decisions",
        sa.Column("resolution_note", sa.String(length=500), nullable=True),
    )
    # SQLite (the zero-setup local/test DB) cannot ALTER-ADD a constraint, and it
    # does not enforce foreign keys here anyway; add the FK only where supported
    # (PostgreSQL in production).
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_decisions_resolved_by_users",
            "scheduling_decisions",
            "users",
            ["resolved_by"],
            ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_decisions_resolved_by_users", "scheduling_decisions", type_="foreignkey"
        )
    op.drop_column("scheduling_decisions", "resolution_note")
    op.drop_column("scheduling_decisions", "resolved_by")
    op.drop_column("scheduling_decisions", "resolved_at")
