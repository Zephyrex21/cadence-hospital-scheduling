"""Operational dashboard endpoint (any authenticated staff)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.base import utcnow
from app.models.user import User
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import summary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_summary(
    now: datetime | None = Query(default=None, description="Defaults to current UTC time."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DashboardSummary:
    return DashboardSummary.model_validate(summary(db, now or utcnow()))
