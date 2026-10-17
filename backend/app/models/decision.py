"""Scheduling decision record — the engine's full, replayable audit artifact.

One row per committed emergency insertion (and per escalation). It stores the
input snapshot, the chosen plan, the alternatives considered, and the parameter
snapshot, so any decision can be explained and reproduced after the fact.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import utcnow


class SchedulingDecision(Base):
    __tablename__ = "scheduling_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False)  # e.g. emergency_insert
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # auto_committed|escalated
    engine_version: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    # The emergency appointment created when auto-committed (null when escalated).
    emergency_appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    # Dedupe key so a double-clicked commit cannot apply twice.
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)

    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    chosen_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    alternatives: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    # Escalation lifecycle: an escalated decision is "resolved" once a nurse or
    # administrator records how it was handled (null while still pending). The
    # dashboard surfaces unresolved escalations from any day until this is set.
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
