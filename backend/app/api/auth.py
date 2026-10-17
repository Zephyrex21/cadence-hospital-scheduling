"""Authentication endpoints: login, refresh, and current user."""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import AuthError
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
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate(db, body.email, body.password)
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
