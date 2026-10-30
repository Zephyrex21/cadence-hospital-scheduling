"""Server-authoritative clock.

Scheduling decisions depend on "now" (response windows, anchors, triage
freshness). That must come from the server: a client-supplied ``now`` is honoured
only when ``CADENCE_ALLOW_CLIENT_NOW`` is enabled (tests / deterministic E2E).
"""

from __future__ import annotations

from datetime import datetime

from app.core.config import settings
from app.models.base import ensure_aware_utc, utcnow


def resolve_now(client_now: datetime | None = None) -> datetime:
    """Return the instant the engine should treat as "now"."""
    if client_now is not None and settings.allow_client_now:
        return ensure_aware_utc(client_now)
    return utcnow()
