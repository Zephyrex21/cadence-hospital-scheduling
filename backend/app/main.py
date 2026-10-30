"""FastAPI application entrypoint.

Mounts the domain routers (auth, patients) and registers the typed error handler.
Further modules (scheduling, triage, dashboard, …) are added in later phases.
"""

from __future__ import annotations

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
from app.api.scheduling import router as scheduling_router
from app.core.config import settings
from app.core.errors import AppError, app_error_handler
from app.core.migrate import run_migrations


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.auto_migrate:
        run_migrations()
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
