"""Integrity guards and request binding.

* DB-level protection against double-booking (PostgreSQL exclusion constraints /
  SQLite triggers) for both the doctor and the patient.
* ``triage_assessments.consumed_at`` — one assessment authorises one emergency.
* ``scheduling_decisions.request_hash`` — binds an idempotency key to its request.

Existing data: the overlap guards cannot be added while active appointments
already overlap (same doctor, or same patient). Such rows are invalid by
definition — they are exactly the double-bookings this migration prevents — so
the migration keeps the earliest-created appointment of each conflicting group and
marks the later ones ``cancelled`` (never deletes), logging every id it touched.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import logging

import sqlalchemy as sa

from alembic import op
from app.models import overlap_guard

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


log = logging.getLogger("alembic.runtime.migration")


def _cancel_existing_overlaps() -> None:
    """Greedy, id-ordered: keep an appointment unless it overlaps one already kept."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, doctor_id, patient_id, scheduled_start, scheduled_end "
            "FROM appointments WHERE status IN ('booked','checked_in','in_progress') "
            "ORDER BY id"
        )
    ).fetchall()
    kept_by_doctor: dict[int, list[tuple[object, object]]] = {}
    kept_by_patient: dict[int, list[tuple[object, object]]] = {}
    cancel: list[int] = []
    for appt_id, doctor_id, patient_id, start, end in rows:
        clash = any(
            start < k_end and k_start < end for k_start, k_end in kept_by_doctor.get(doctor_id, [])
        ) or any(
            start < k_end and k_start < end
            for k_start, k_end in kept_by_patient.get(patient_id, [])
        )
        if clash:
            cancel.append(appt_id)
        else:
            kept_by_doctor.setdefault(doctor_id, []).append((start, end))
            kept_by_patient.setdefault(patient_id, []).append((start, end))
    if cancel:
        log.warning(
            "0005: cancelling %d pre-existing overlapping appointment(s): %s",
            len(cancel),
            cancel,
        )
        bind.execute(
            sa.text(
                "UPDATE appointments SET status = 'cancelled' WHERE id IN :ids"
            ).bindparams(sa.bindparam("ids", expanding=True)),
            {"ids": cancel},
        )


def upgrade() -> None:
    op.add_column(
        "triage_assessments", sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "scheduling_decisions", sa.Column("request_hash", sa.String(length=64), nullable=True)
    )

    _cancel_existing_overlaps()

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
