"""Authentication endpoints: login, refresh, and current user."""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import AuthError
from app.core.ratelimit import login_throttle
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User) -> TokenResponse:
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject, user.role.value),
        refresh_token=create_refresh_token(subject, user.role.value),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    email = body.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    pair_key, email_key = f"{ip}|{email}", f"email|{email}"
    window = settings.login_window_sec
    # Per client+email is strict; per-email alone is looser so an attacker cannot
    # trivially lock a real user out from a single address.
    login_throttle.check(pair_key, limit=settings.login_max_attempts, window_sec=window)
    login_throttle.check(email_key, limit=settings.login_max_attempts * 4, window_sec=window)
    try:
        user = authenticate(db, body.email, body.password)
    except AuthError:
        login_throttle.fail(pair_key)
        login_throttle.fail(email_key)
        raise
    login_throttle.reset(pair_key)
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        payload = decode_token(body.refresh_token)
    except jwt.ExpiredSignatureError:
        raise AuthError("Refresh token has expired") from None
    except jwt.PyJWTError:
        raise AuthError("Invalid refresh token") from None

    if payload.get("type") != "refresh":
        raise AuthError("Expected a refresh token")

    subject = payload.get("sub")
    user = db.get(User, int(subject)) if subject is not None else None
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return _issue_tokens(user)


@router.get("/me", response_model=UserRead)
def me(current: User = Depends(get_current_user)) -> User:
    return current
