"""Integrity guards and request binding.

* DB-level protection against double-booking (PostgreSQL exclusion constraints /
  SQLite triggers) for both the doctor and the patient.
* ``triage_assessments.consumed_at`` — one assessment authorises one emergency.
* ``scheduling_decisions.request_hash`` — binds an idempotency key to its request.

NOTE: adding the overlap guards fails if existing rows already overlap. Resolve
those first (cancel/move the duplicates), then re-run the migration.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.models import overlap_guard

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "triage_assessments", sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "scheduling_decisions", sa.Column("request_hash", sa.String(length=64), nullable=True)
    )

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(overlap_guard.PG_EXTENSION)
        op.execute(
            overlap_guard.pg_add_constraint_sql(overlap_guard.PG_DOCTOR_CONSTRAINT, "doctor_id")
        )
        op.execute(
            overlap_guard.pg_add_constraint_sql(overlap_guard.PG_PATIENT_CONSTRAINT, "patient_id")
        )
    elif dialect == "sqlite":
        for stmt in overlap_guard.sqlite_trigger_statements():
            op.execute(stmt)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        for name in (overlap_guard.PG_PATIENT_CONSTRAINT, overlap_guard.PG_DOCTOR_CONSTRAINT):
            op.execute(f"ALTER TABLE appointments DROP CONSTRAINT IF EXISTS {name}")
    elif dialect == "sqlite":
        for stmt in overlap_guard.SQLITE_DROP_TRIGGERS:
            op.execute(stmt)
    op.drop_column("scheduling_decisions", "request_hash")
    op.drop_column("triage_assessments", "consumed_at")
