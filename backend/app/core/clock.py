"""Server-authoritative clock.

Scheduling decisions depend on "now" (response windows, anchors, triage
freshness). That must come from the server: a client-supplied ``now`` is honoured
only when ``CADENCE_ALLOW_CLIENT_NOW`` is enabled (tests / deterministic E2E).
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from app.core.config import settings
from app.models.base import ensure_aware_utc, utcnow


def resolve_now(client_now: datetime | None = None) -> datetime:
    """Return the instant the engine should treat as "now"."""
    if client_now is not None and settings.allow_client_now:
        return ensure_aware_utc(client_now)
    return utcnow()


def clinic_day_bounds(day: datetime) -> tuple[datetime, datetime]:
    """UTC ``[start, end)`` of the *clinic-local* calendar day containing ``day``.

    "Today" for an Indian clinic starts at 00:00 IST (18:30 UTC the evening
    before) — slicing by UTC midnight would show yesterday's date for the first
    5½ hours of every IST day and split a late shift across two "days".
    """
    tz = settings.clinic_tz
    local = ensure_aware_utc(day).astimezone(tz)
    start_local = datetime.combine(local.date(), time.min, tzinfo=tz)
    end_local = datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)
