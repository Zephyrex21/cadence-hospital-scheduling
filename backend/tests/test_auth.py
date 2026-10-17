"""Authentication endpoint tests."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.core.enums import Role
from app.models.user import User


def test_login_success_returns_tokens(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user_factory(Role.RECEPTIONIST, email="rosa@example.com", password="hunter2!")
    resp = client.post(
        "/auth/login", json={"email": "rosa@example.com", "password": "hunter2!"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


def test_login_wrong_password_is_401(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user_factory(Role.RECEPTIONIST, email="rosa@example.com", password="hunter2!")
    resp = client.post(
        "/auth/login", json={"email": "rosa@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_me_requires_token(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401


def test_me_returns_current_user(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    user = user_factory(Role.DOCTOR, email="amara@example.com")
    resp = client.get("/auth/me", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["email"] == "amara@example.com"
    assert resp.json()["role"] == "doctor"


def test_refresh_rotates_tokens(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user_factory(Role.ADMINISTRATOR, email="admin@example.com", password="pw12345")
    login = client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "pw12345"}
    ).json()

    resp = client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_access_token_rejected_as_refresh(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user_factory(Role.ADMINISTRATOR, email="admin@example.com", password="pw12345")
    login = client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "pw12345"}
    ).json()

    resp = client.post("/auth/refresh", json={"refresh_token": login["access_token"]})
    assert resp.status_code == 401
