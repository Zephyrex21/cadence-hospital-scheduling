"""Database-level protection against double-booking.

Application-level "check, then insert" is racy: two concurrent requests can both
see a free slot. These guards make the *database* refuse the second write:

* PostgreSQL (production) — GiST exclusion constraints
  (``EXCLUDE USING gist (doctor_id WITH =, tstzrange(start, end) WITH &&)``), one
  for the doctor and one for the patient, both restricted to active statuses.
* SQLite (zero-setup local dev / tests) — equivalent BEFORE INSERT/UPDATE triggers.

Active = the appointment still occupies time (booked, checked_in, in_progress).
A violation surfaces as ``sqlalchemy.exc.IntegrityError``; the services turn it
into a friendly 409.
"""

from __future__ import annotations

from sqlalchemy import DDL as _DDL
from sqlalchemy import event
from sqlalchemy.schema import Table


def DDL(statement: str) -> _DDL:  # noqa: N802 - mirrors sqlalchemy's name
    return _DDL(statement)  # type: ignore[no-untyped-call]


ACTIVE_SQL = "'booked','checked_in','in_progress'"

PG_EXTENSION = "CREATE EXTENSION IF NOT EXISTS btree_gist"
PG_DOCTOR_CONSTRAINT = "ex_appointments_doctor_no_overlap"
PG_PATIENT_CONSTRAINT = "ex_appointments_patient_no_overlap"


def pg_add_constraint_sql(name: str, column: str) -> str:
    return (
        f"ALTER TABLE appointments ADD CONSTRAINT {name} EXCLUDE USING gist "
        f"({column} WITH =, tstzrange(scheduled_start, scheduled_end, '[)') WITH &&) "
        f"WHERE (status IN ({ACTIVE_SQL}))"
    )


def _sqlite_trigger_sql(name: str, column: str, kind: str) -> str:
    if kind == "insert":
        head = "BEFORE INSERT ON appointments"
        same_row = ""
    else:
        head = (
            "BEFORE UPDATE OF "
            f"{column}, scheduled_start, scheduled_end, status ON appointments"
        )
        same_row = "AND a.id <> NEW.id "
    return (
        f"CREATE TRIGGER IF NOT EXISTS {name}_{kind[:3]} {head} "
        f"WHEN NEW.status IN ({ACTIVE_SQL}) "
        "BEGIN "
        f"SELECT RAISE(ABORT, 'appointment_overlap:{column}') WHERE EXISTS ("
        "SELECT 1 FROM appointments a "
        f"WHERE a.{column} = NEW.{column} {same_row}"
        f"AND a.status IN ({ACTIVE_SQL}) "
        "AND a.scheduled_start < NEW.scheduled_end "
        "AND NEW.scheduled_start < a.scheduled_end); "
        "END"
    )


def sqlite_trigger_statements() -> list[str]:
    stmts: list[str] = []
    for name, column in (
        ("trg_appt_no_doctor_overlap", "doctor_id"),
        ("trg_appt_no_patient_overlap", "patient_id"),
    ):
        for kind in ("insert", "update"):
            stmts.append(_sqlite_trigger_sql(name, column, kind))
    return stmts


SQLITE_DROP_TRIGGERS = [
    f"DROP TRIGGER IF EXISTS {name}_{kind}"
    for name in ("trg_appt_no_doctor_overlap", "trg_appt_no_patient_overlap")
    for kind in ("ins", "upd")
]


def install(table: Table) -> None:
    """Attach the guards to ``create_all`` so tests / e2e / fresh DBs get them too."""
    event.listen(
        table, "before_create", DDL(PG_EXTENSION).execute_if(dialect="postgresql")
    )
    for name, column in (
        (PG_DOCTOR_CONSTRAINT, "doctor_id"),
        (PG_PATIENT_CONSTRAINT, "patient_id"),
    ):
        event.listen(
            table,
            "after_create",
            DDL(pg_add_constraint_sql(name, column)).execute_if(dialect="postgresql"),
        )
    for stmt in sqlite_trigger_statements():
        event.listen(table, "after_create", DDL(stmt).execute_if(dialect="sqlite"))
