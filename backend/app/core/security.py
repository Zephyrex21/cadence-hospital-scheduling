"""Password hashing (argon2) and JWT access/refresh token handling.

Argon2 is preferred over bcrypt (memory-hard, no 72-byte truncation). Tokens are
signed with HS256 using ``settings.jwt_secret`` and carry the user id (``sub``),
``role``, and a ``type`` claim distinguishing access from refresh tokens.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()

TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def _create_token(subject: str, role: str, token_type: TokenType, ttl_min: int) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_min)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(subject, role, "access", settings.access_token_ttl_min)


def create_refresh_token(subject: str, role: str) -> str:
    return _create_token(subject, role, "refresh", settings.refresh_token_ttl_min)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a token's signature and expiry. Raises on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
