"""Throwaway backend process for the Playwright E2E.

Resets a SQLite database, seeds the deterministic signature-flow data, then
serves the API on port 8000. It refuses to run against anything but SQLite so it
can never drop or reseed a real database.

Run (from the ``backend`` directory):
    CADENCE_DATABASE_URL=sqlite+pysqlite:///./e2e.db uv run python -m app.e2e_server
"""

from __future__ import annotations

import uvicorn

import app.models  # noqa: F401  -- register all models on Base.metadata
from app.core.config import settings
from app.core.db import Base, engine
from app.e2e_seed import seed_e2e


def main() -> None:
    if "sqlite" not in settings.database_url:
        raise SystemExit(
            "e2e_server refuses to run: CADENCE_DATABASE_URL must be a sqlite URL "
            f"(got {settings.database_url!r}), so it never touches a real database."
        )
    settings.auto_migrate = False  # this process builds its own schema below
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed_e2e()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
