"""FastAPI application entrypoint.

Mounts the domain routers (auth, patients) and registers the typed error handler.
Further modules (scheduling, triage, dashboard, …) are added in later phases.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.auth import router as auth_router
from app.api.consultation import router as consultation_router
from app.api.dashboard import router as dashboard_router
from app.api.emergency import router as emergency_router
from app.api.health import router as health_router
from app.api.history import router as history_router
from app.api.patients import router as patients_router
from app.api.profiles import router as profiles_router
from app.api.scheduling import router as scheduling_router
from app.core.config import settings
from app.core.errors import AppError, app_error_handler
from app.core.migrate import run_migrations

_log = logging.getLogger("uvicorn.error.cadence.main")


def _bootstrap_mongo() -> None:
    """Validators + indexes, demo profiles, then backfill — all idempotent.

    Runs in a background thread so a slow or unreachable Atlas can never delay the API
    from accepting requests (this matters on a free host's cold start).
    """
    from app.core.db import SessionLocal
    from app.core.mongo import get_mongo_db
    from app.mongo.schema import ensure_mongo_schema
    from app.seed_profiles import seed_profiles
    from app.services.profiles import backfill_profiles

    try:
        mdb = get_mongo_db()
        if mdb is None:
            return
        ensure_mongo_schema(mdb)
        db = SessionLocal()
        try:
            if settings.seed_demo_on_start:
                seed_profiles(db, mdb)  # before backfill, so demo docs are built in full
            counts = backfill_profiles(db, mdb)
        finally:
            db.close()
        _log.info("MongoDB profile store ready (backfilled %s).", counts)
    except Exception:  # noqa: BLE001 - the profile store is optional; never take the API down
        _log.exception("MongoDB bootstrap failed; profiles are unavailable until it succeeds")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.auto_migrate:
        run_migrations()
    if settings.seed_demo_on_start:
        from app.seed import refresh_demo_data

        refresh_demo_data()
    if settings.mongodb_uri.strip():
        threading.Thread(target=_bootstrap_mongo, name="mongo-bootstrap", daemon=True).start()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(patients_router)
    app.include_router(profiles_router)
    app.include_router(scheduling_router)
    app.include_router(emergency_router)
    app.include_router(consultation_router)
    app.include_router(history_router)
    app.include_router(dashboard_router)

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "version": __version__, "docs": "/docs"}

    return app


app = create_app()
