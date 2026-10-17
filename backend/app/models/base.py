"""Common model mixins."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeEngine


def utcnow() -> datetime:
    """Timezone-aware current time in UTC (storage is always UTC)."""
    return datetime.now(UTC)


def ensure_aware_utc(value: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC.

    Inbound values (API query params, client payloads) may be naive. A naive
    value is treated as already-UTC and given the zone; an aware value is
    converted to UTC. This keeps every instant that reaches the pure engine on
    the same footing, so comparisons never mix naive and aware datetimes.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class UtcDateTime(TypeDecorator[datetime]):
    """A datetime column that is always timezone-aware UTC in Python.

    SQLite discards ``tzinfo`` on read, so a value stored as aware returns naive
    and can no longer be compared against :func:`utcnow`. This decorator stores
    UTC (timezone-aware on PostgreSQL, naive-UTC elsewhere) and *always* yields a
    timezone-aware UTC value on the way out — the root cause of the engine's
    "can't compare offset-naive and offset-aware datetimes" errors.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(DateTime(timezone=True))
        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        value = ensure_aware_utc(value)
        # PostgreSQL (TIMESTAMPTZ) keeps the zone; elsewhere store naive-UTC.
        return value if dialect.name == "postgresql" else value.replace(tzinfo=None)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        dt: datetime = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` with Python-side UTC defaults.

    Python-side defaults (rather than ``server_default=func.now()``) keep behavior
    identical across PostgreSQL and the SQLite engine used in tests.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
