"""Liveness endpoint.

Deliberately dependency-free: it reports that the API process is up, without touching
the database. Readiness checks that probe dependencies arrive in a later phase.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from pymongo.errors import PyMongoError

from app.core.mongo import get_mongo_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="cadence-api")


class MongoHealth(BaseModel):
    enabled: bool
    ok: bool


@router.get("/health/mongo", response_model=MongoHealth)
def health_mongo() -> MongoHealth:
    """Is the optional MongoDB profile store configured, and does it answer?

    Separate from ``/health`` on purpose: the wake-up pings must never depend on Atlas.
    """
    mdb = get_mongo_db()
    if mdb is None:
        return MongoHealth(enabled=False, ok=False)
    try:
        mdb.command("ping")
    except PyMongoError:
        return MongoHealth(enabled=True, ok=False)
    return MongoHealth(enabled=True, ok=True)
