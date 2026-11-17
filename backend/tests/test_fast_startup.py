"""A sleeping free-tier host must reach "accepting requests" quickly: the demo-data refresh
(hundreds of queries on a slow remote database) may not hold up the first /health answer."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.enums import Role
from app.main import app


@pytest.fixture()
def lifespan_env(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Any:
    import app.core.db as db_mod

    monkeypatch.setattr(
        db_mod, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)
    )
    monkeypatch.setattr(settings, "seed_demo_on_start", True)
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(settings, "mongodb_uri", "")
    return monkeypatch


def test_existing_data_means_the_seed_never_delays_startup(
    db_session: Session, user_factory: Any, lifespan_env: pytest.MonkeyPatch
) -> None:
    import app.seed as seed_mod

    user_factory(Role.ADMINISTRATOR, email="exists@cadence.dev")  # the demo was seeded before
    started, release = threading.Event(), threading.Event()

    def slow_refresh() -> None:
        started.set()
        release.wait(timeout=10)  # a seed that takes "forever" on a slow host

    lifespan_env.setattr(seed_mod, "refresh_demo_data", slow_refresh)
    t0 = time.monotonic()
    with TestClient(app) as client:  # entering runs the lifespan startup
        up_after = time.monotonic() - t0
        assert client.get("/health").json()["status"] == "ok"
        assert started.wait(timeout=5), "the refresh should still run, in the background"
        assert up_after < 2.0  # not blocked on the 10-second "seed"
        release.set()


def test_a_brand_new_database_is_seeded_before_serving(
    db_session: Session, lifespan_env: pytest.MonkeyPatch
) -> None:
    import app.seed as seed_mod

    calls: list[str] = []
    lifespan_env.setattr(seed_mod, "refresh_demo_data", lambda: calls.append("seeded"))
    with TestClient(app) as client:
        # No users yet: the first visitor must be able to sign in, so the seed ran first.
        assert calls == ["seeded"]
        assert client.get("/health").status_code == 200


def test_seed_failure_in_the_background_never_takes_the_api_down(
    db_session: Session, user_factory: Any, lifespan_env: pytest.MonkeyPatch
) -> None:
    import app.seed as seed_mod

    user_factory(Role.ADMINISTRATOR, email="exists2@cadence.dev")
    done = threading.Event()

    def boom() -> None:
        done.set()
        raise RuntimeError("database hiccup")

    lifespan_env.setattr(seed_mod, "refresh_demo_data", boom)
    with TestClient(app) as client:
        assert done.wait(timeout=5)
        assert client.get("/health").json()["status"] == "ok"
