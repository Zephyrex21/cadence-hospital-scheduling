"""Shared domain enumerations.

Kept in one place so every module (and the scheduling engine in later phases)
references the same vocabulary. Values are stored as strings in the database.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    RECEPTIONIST = "receptionist"
    TRIAGE_NURSE = "triage_nurse"
    DOCTOR = "doctor"
    ADMINISTRATOR = "administrator"


class AuditAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    CANCEL = "cancel"
    RESOLVE = "resolve"


class AppointmentStatus(StrEnum):
    """Lifecycle of an appointment. The scheduling engine (later phases) treats
    IN_PROGRESS as protected and never displaces it."""

    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    DISPLACED = "displaced"


class AppointmentOrigin(StrEnum):
    """How the appointment entered the schedule."""

    BOOKED = "booked"
    WALK_IN = "walk_in"
    EMERGENCY = "emergency"


class Acuity(StrEnum):
    """Operational triage acuity — a human nurse's judgment, never a diagnosis.

    Ordered most-urgent (A1) to least-urgent (A5). The scheduling engine uses this
    to set response-time targets and the priority-inversion guard. A1 is always
    human-directed (it may require interrupting a consultation), so the engine
    escalates rather than auto-committing it.
    """

    A1 = "a1"  # critical / resuscitation
    A2 = "a2"  # emergent
    A3 = "a3"  # urgent
    A4 = "a4"  # semi-urgent
    A5 = "a5"  # non-urgent / routine


class ConsultationAction(StrEnum):
    """A doctor's consultation-status transition."""

    CHECK_IN = "check_in"
    START = "start"
    COMPLETE = "complete"
    NO_SHOW = "no_show"
