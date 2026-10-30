"""Per-doctor serialisation of schedule writes.

On PostgreSQL we take a transaction-scoped advisory lock per doctor so concurrent
bookings / emergency commits for the same doctor queue up and each re-reads the
schedule *after* the previous one committed (READ COMMITTED), turning a would-be
race into a clean "slot no longer available" answer. The exclusion constraints
(see ``models.overlap_guard``) remain the final, unbypassable guarantee, and are
the only guard on SQLite (single-writer anyway).
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

_NAMESPACE = 7_351  # arbitrary app-wide key space for doctor schedule locks


def lock_doctors(db: Session, doctor_ids: Iterable[int]) -> None:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Sorted acquisition order prevents deadlocks between overlapping lock sets.
    for doctor_id in sorted(set(doctor_ids)):
        db.execute(
            text("SELECT pg_advisory_xact_lock(:ns, :id)"),
            {"ns": _NAMESPACE, "id": doctor_id},
        )
