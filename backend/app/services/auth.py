"""Authentication service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AuthError, ForbiddenError
from app.core.security import hash_password, verify_password
from app.models.user import User

_dummy_hash: str | None = None


def _burn_a_verification(password: str) -> None:
    """Spend the same time as a real password check, so an unknown email can't be told apart
    from a wrong password by how long the response takes."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-account")
    verify_password(password, _dummy_hash)


def authenticate(db: Session, email: str, password: str) -> User:
    """Return the user for valid credentials, else raise.

    The same error is returned for an unknown email and a wrong password so the
    endpoint does not reveal which emails exist.
    """
    # Emails are case-insensitive in practice (phone keyboards capitalise the first letter).
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == normalized))
    if user is None:
        _burn_a_verification(password)
        raise AuthError("Invalid email or password", details={"code": "invalid_credentials"})
    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password", details={"code": "invalid_credentials"})
    if not user.is_active:
        raise ForbiddenError("This account is disabled")
    return user
