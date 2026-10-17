"""Authentication service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AuthError, ForbiddenError
from app.core.security import verify_password
from app.models.user import User


def authenticate(db: Session, email: str, password: str) -> User:
    """Return the user for valid credentials, else raise.

    The same error is returned for an unknown email and a wrong password so the
    endpoint does not reveal which emails exist.
    """
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password", details={"code": "invalid_credentials"})
    if not user.is_active:
        raise ForbiddenError("This account is disabled")
    return user
