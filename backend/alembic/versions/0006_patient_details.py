"""Richer patient record: city, blood group, emergency contact, notes.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("city", sa.String(length=80), nullable=True))
    op.add_column("patients", sa.Column("blood_group", sa.String(length=8), nullable=True))
    op.add_column(
        "patients", sa.Column("emergency_contact", sa.String(length=160), nullable=True)
    )
    op.add_column("patients", sa.Column("notes", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "notes")
    op.drop_column("patients", "emergency_contact")
    op.drop_column("patients", "blood_group")
    op.drop_column("patients", "city")
