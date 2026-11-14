"""Authentication endpoints: login, refresh, and current user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.clientip import client_ip
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import AuthError, RateLimitError
from app.core.ratelimit import login_throttle
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth import authenticate
from app.services.tokens import issue_pair, revoke, rotate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    email = body.email.strip().lower()
    ip = client_ip(request)
    pair_key, email_key = f"{ip}|{email}", f"email|{email}"
    window = settings.login_window_sec
    # Per client+email is strict: that client is blocked after a few failures.
    login_throttle.check(pair_key, limit=settings.login_max_attempts, window_sec=window)
    # Per-email is a flood detector. It must NOT lock the real owner out (the demo accounts are
    # published on the login page, so anyone could otherwise block them): during a flood, wrong
    # guesses are throttled but the correct password still signs in.
    flood = login_throttle.lockout_remaining(
        email_key, limit=settings.login_max_attempts * 4, window_sec=window
    )
    try:
        user = authenticate(db, body.email, body.password)
    except AuthError:
        login_throttle.fail(pair_key)
        login_throttle.fail(email_key)
        if flood:
            raise RateLimitError(
                "Too many failed sign-in attempts. Try again later.", retry_after=flood
            ) from None
        raise
    login_throttle.reset(pair_key)
    return issue_pair(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange a refresh token for a new pair. Each refresh token works exactly once."""
    return rotate(db, body.refresh_token)


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: Session = Depends(get_db)) -> Response:
    """Revoke the refresh token so a copy of it is useless after sign-out."""
    revoke(db, body.refresh_token)
    return Response(status_code=204)


@router.get("/me", response_model=UserRead)
def me(current: User = Depends(get_current_user)) -> User:
    return current
