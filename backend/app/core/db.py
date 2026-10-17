"""Database engine, session factory, and the FastAPI session dependency.

We use **synchronous** SQLAlchemy 2.0. Sync keeps the code simple and makes the
transactional row-locking the scheduling engine needs in later phases (``SELECT
... FOR UPDATE``) straightforward to reason about. FastAPI runs sync endpoints in
a threadpool, which is ample for this workload.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ``create_engine`` is lazy — it does not open a connection until first use, so
# importing this module never requires a running database (tests override the
# session dependency with their own in-memory engine).
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Iterator[Session]:
    """Yield a scoped database session for the lifetime of a request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
