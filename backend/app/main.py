"""FastAPI application entrypoint.

Mounts the domain routers (auth, patients) and registers the typed error handler.
Further modules (scheduling, triage, dashboard, …) are added in later phases.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.auth import router as auth_router
from app.api.consultation import router as consultation_router
from app.api.dashboard import router as dashboard_router
from app.api.emergency import router as emergency_router
from app.api.health import router as health_router
from app.api.history import router as history_router
from app.api.notifications import router as notifications_router
from app.api.patients import router as patients_router
from app.api.profiles import router as profiles_router
from app.api.scheduling import router as scheduling_router
from app.core.config import settings
from app.core.errors import (
    AppError,
    app_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
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


def _demo_data_exists() -> bool:
    """Has the demo staff already been seeded? (Decides whether a refresh can wait.)"""
    from sqlalchemy import func, select

    from app.core.db import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        return (db.scalar(select(func.count(User.id))) or 0) > 0
    except Exception:  # noqa: BLE001 - unknown state: be safe and seed before serving
        return False
    finally:
        db.close()


def _background_startup() -> None:
    """Slow, non-essential start-up work that must not delay the first response."""
    try:
        if settings.seed_demo_on_start:
            from app.seed import refresh_demo_data

            refresh_demo_data()
        if settings.mongodb_uri.strip():
            _bootstrap_mongo()  # after the seed: profile docs are built from fresh rows
    except Exception:  # noqa: BLE001 - background work must never take the API down
        _log.exception("Background start-up work failed; the API keeps running")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Get to "accepting requests" as fast as possible.

    The API runs on a free host that sleeps when idle, and every second of start-up is a second
    the user stares at the "waking up" notice. So: migrations run first (the schema must be
    right), but refreshing the demo data — hundreds of queries on a slow, remote database —
    happens in the background once the app is already answering ``/health``. The one exception
    is a brand-new database with no users yet: there the seed runs first so the very first
    visitor can sign in.
    """
    if settings.auto_migrate:
        run_migrations()
    if settings.seed_demo_on_start and not _demo_data_exists():
        from app.seed import refresh_demo_data

        refresh_demo_data()
        threading.Thread(
            target=_bootstrap_mongo_only, name="startup-mongo", daemon=True
        ).start()
    else:
        threading.Thread(target=_background_startup, name="startup", daemon=True).start()
    yield


def _bootstrap_mongo_only() -> None:
    if settings.mongodb_uri.strip():
        _bootstrap_mongo()


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
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        # JSON API only: it must never be sniffed, framed, or cached (it carries patient data).
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if request.url.path not in ("/docs", "/redoc", "/openapi.json"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(patients_router)
    app.include_router(profiles_router)
    app.include_router(scheduling_router)
    app.include_router(emergency_router)
    app.include_router(consultation_router)
    app.include_router(history_router)
    app.include_router(notifications_router)
    app.include_router(dashboard_router)

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "version": __version__, "docs": "/docs"}

    return app


app = create_app()
