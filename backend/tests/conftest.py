"""Shared test fixtures.

Each test gets a fresh in-memory SQLite database (StaticPool keeps a single
shared connection so the schema persists across sessions within one test). The
FastAPI ``get_db`` dependency is overridden to use the test session.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  -- register models on Base.metadata
from app.core.db import Base, get_db
from app.core.enums import Role
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def user_factory(db_session: Session) -> Callable[..., User]:
    def make(role: Role, *, email: str | None = None, password: str = "secret123") -> User:
        user = User(
            name=role.value.replace("_", " ").title(),
            email=email or f"{role.value}@example.com",
            role=role,
            password_hash=hash_password(password),
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return make


@pytest.fixture()
def auth_headers() -> Callable[[User], dict[str, str]]:
    def make(user: User) -> dict[str, str]:
        token = create_access_token(str(user.id), user.role.value)
        return {"Authorization": f"Bearer {token}"}

    return make
