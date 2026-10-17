"""Reusable FastAPI dependencies: authenticated user and role guards.

Authorization is enforced here, server-side, on every protected route. The
frontend hiding controls is cosmetic only.
"""

from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.enums import Role
from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_token
from app.models.user import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise AuthError("Missing bearer token")
    token = header.split(" ", 1)[1].strip()

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired") from None
    except jwt.PyJWTError:
        raise AuthError("Could not validate token") from None

    if payload.get("type") != "access":
        raise AuthError("Expected an access token")

    subject = payload.get("sub")
    user = db.get(User, int(subject)) if subject is not None else None
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    """Dependency factory: allow only the given roles, else 403."""

    def guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("You do not have permission to perform this action")
        return user

    return guard
