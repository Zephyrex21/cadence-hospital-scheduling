"""MongoDB Atlas connection (optional profile store).

Postgres stays the system of record for identity, auth and scheduling; MongoDB holds
the descriptive patient / staff profiles. The client is created lazily and with short
timeouts so an unreachable Atlas can never hang a request (or a cold start).
"""

from __future__ import annotations

import threading
from typing import Any

from pymongo import MongoClient

from app.core.config import settings

_client: MongoClient[dict[str, Any]] | None = None
_lock = threading.Lock()
_override: Any = None  # test seam (mongomock)


def set_mongo_override(database: Any) -> None:
    global _override
    _override = database


def mongo_enabled() -> bool:
    return _override is not None or bool(settings.mongodb_uri.strip())


def get_mongo_db() -> Any | None:
    """The database, or ``None`` when MongoDB isn't configured. Also a FastAPI dependency."""
    global _client
    if _override is not None:
        return _override
    uri = settings.mongodb_uri.strip()
    if not uri:
        return None
    with _lock:
        if _client is None:
            _client = MongoClient(
                uri,
                serverSelectionTimeoutMS=3_000,
                connectTimeoutMS=3_000,
                socketTimeoutMS=10_000,
                appname="cadence-api",
                tz_aware=True,
            )
    return _client[settings.mongodb_db]
