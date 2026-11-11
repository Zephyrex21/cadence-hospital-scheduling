"""Issuing and rotating tokens.

Refresh tokens are single-use: exchanging one marks it used and issues a fresh pair. A token
presented again *after a short grace window* means it was copied — every outstanding token of
that user is revoked and they must sign in again. (The grace window absorbs two browser tabs
refreshing at the same instant, which is a harmless race, not theft.)
"""

from __future__ import annotations

from datetime import timedelta

import jwt
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.core.errors import AuthError
from app.core.security import create_access_token, decode_token, new_refresh_token
from app.models.base import ensure_aware_utc, utcnow
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenResponse

REUSE_GRACE = timedelta(seconds=10)


def issue_pair(db: Session, user: User) -> TokenResponse:
    subject = str(user.id)
    refresh, jti, expires = new_refresh_token(subject, user.role.value)
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires))
    # housekeeping: forget this user's long-expired tokens
    db.execute(
        delete(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.expires_at < utcnow())
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return TokenResponse(
        access_token=create_access_token(subject, user.role.value), refresh_token=refresh
    )


def _decode_refresh(token: str) -> dict[str, object]:
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthError("Refresh token has expired") from None
    except jwt.PyJWTError:
        raise AuthError("Invalid refresh token") from None
    if payload.get("type") != "refresh":
        raise AuthError("Expected a refresh token")
    return payload


def rotate(db: Session, token: str) -> TokenResponse:
    payload = _decode_refresh(token)
    subject = payload.get("sub")
    user = db.get(User, int(str(subject))) if subject is not None else None
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")

    jti = payload.get("jti")
    if jti is not None:  # tokens issued before rotation existed have no id: accept them once
        row = db.get(RefreshToken, str(jti), with_for_update=True)
        if row is None or row.user_id != user.id:
            raise AuthError("Invalid refresh token")
        now = utcnow()
        if row.used_at is not None:
            if now - ensure_aware_utc(row.used_at) > REUSE_GRACE:
                db.execute(
                    update(RefreshToken)
                    .where(RefreshToken.user_id == user.id, RefreshToken.used_at.is_(None))
                    .values(used_at=now)
                    .execution_options(synchronize_session=False)
                )
                db.commit()
                raise AuthError("Refresh token reuse detected. Please sign in again.")
            raise AuthError("Refresh token already used")
        row.used_at = now
    return issue_pair(db, user)


def revoke(db: Session, token: str) -> None:
    """Sign-out: make this refresh token unusable. Silent for anything unrecognised."""
    try:
        payload = _decode_refresh(token)
    except AuthError:
        return
    jti = payload.get("jti")
    if jti is None:
        return
    row = db.get(RefreshToken, str(jti))
    if row is not None and row.used_at is None:
        row.used_at = utcnow()
        db.commit()
