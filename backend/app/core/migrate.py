"""Run ``alembic upgrade head`` from inside the app (startup auto-migration).

Why: the app and its schema must move together. On hosts without a shell or a
release/pre-deploy step, a new release that adds a column would otherwise start
against the old schema and fail on first use. Running migrations at startup makes
every deploy self-contained.

Safety:
* PostgreSQL: a session-level advisory lock serialises concurrent instances, so
  two replicas never run the same migration at once (the second waits, then finds
  nothing to do).
* Each migration is transactional on PostgreSQL (DDL is atomic), so a failure
  leaves the schema at the previous revision. The error is logged and re-raised:
  the deploy then fails its health check and the host keeps the previous version
  serving rather than promoting a half-working release.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from app.core.config import settings

# Child of uvicorn's logger so these lines show up in the host's (Render) log stream.
log = logging.getLogger("uvicorn.error.cadence.migrate")

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_LOCK_KEY = 7_351_001  # arbitrary, distinct from the per-doctor schedule locks


def _alembic_config() -> Config:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False  # keep the host app's logging intact
    return cfg


def run_migrations() -> None:
    """Upgrade the configured database to the latest revision."""
    cfg = _alembic_config()
    url = settings.database_url
    if url.startswith("postgresql"):
        lock_engine = create_engine(url, pool_pre_ping=True)
        with lock_engine.connect() as lock_conn:
            lock_conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _LOCK_KEY})
            try:
                _upgrade(cfg)
            finally:
                lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})
                lock_conn.commit()
        lock_engine.dispose()
    else:
        _upgrade(cfg)


def _upgrade(cfg: Config) -> None:
    log.info("Applying database migrations (alembic upgrade head)...")
    try:
        command.upgrade(cfg, "head")
    except Exception:
        log.exception("Database migration FAILED; refusing to start on a mismatched schema")
        raise
    log.info("Database schema is up to date.")
