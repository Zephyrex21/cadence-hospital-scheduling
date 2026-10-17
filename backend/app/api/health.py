"""Liveness endpoint.

Deliberately dependency-free: it reports that the API process is up, without touching
the database. Readiness checks that probe dependencies arrive in a later phase.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="cadence-api")
